import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const AuthContext = createContext(null);

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [token, setToken] = useState(localStorage.getItem('falconToken'));
    const [loading, setLoading] = useState(true);

    const axiosInstance = axios.create({
        baseURL: API,
        headers: {
            'Content-Type': 'application/json',
        },
    });

    axiosInstance.interceptors.request.use((config) => {
        const storedToken = localStorage.getItem('falconToken');
        if (storedToken) {
            config.headers.Authorization = `Bearer ${storedToken}`;
        }
        return config;
    });

    const fetchUser = useCallback(async () => {
        if (!token) {
            setLoading(false);
            return;
        }
        try {
            const response = await axiosInstance.get('/auth/me');
            setUser(response.data);
        } catch (error) {
            console.error('Auth check failed:', error);
            localStorage.removeItem('falconToken');
            setToken(null);
            setUser(null);
        } finally {
            setLoading(false);
        }
    }, [token]);

    useEffect(() => {
        fetchUser();
    }, [fetchUser]);

    const login = async (email, password) => {
        const response = await axiosInstance.post('/auth/login', { email, password });
        const { access_token, user: userData } = response.data;
        localStorage.setItem('falconToken', access_token);
        setToken(access_token);
        setUser(userData);
        return userData;
    };

    const register = async (email, password, full_name, organization) => {
        const response = await axiosInstance.post('/auth/register', {
            email,
            password,
            full_name,
            organization,
        });
        const { access_token, user: userData } = response.data;
        localStorage.setItem('falconToken', access_token);
        setToken(access_token);
        setUser(userData);
        return userData;
    };

    const logout = () => {
        localStorage.removeItem('falconToken');
        setToken(null);
        setUser(null);
    };

    // Partial profile update (currently full_name/phone) — phone is what lets
    // the Problems console's "Notify Owner" action actually reach this user
    // over SMS. Updates local `user` state so consumers (SettingsPage, the
    // Problems console) see the change without a full reload.
    const updateProfile = async (patch) => {
        const response = await axiosInstance.patch('/auth/me', patch);
        setUser(response.data);
        return response.data;
    };

    const value = {
        user,
        token,
        loading,
        login,
        register,
        logout,
        updateProfile,
        isAuthenticated: !!user,
        isAdmin: user?.role === 'admin',
        isViewer: user?.role === 'viewer',
        canWrite: user?.role === 'admin' || user?.role === 'user',
        api: axiosInstance,
    };

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};
