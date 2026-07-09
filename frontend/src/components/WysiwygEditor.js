import React, { useEffect, useCallback } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Link from '@tiptap/extension-link';
import { Button } from '../components/ui/button';
import {
    Bold, Italic, Underline, List, ListOrdered, Quote, Heading1, Heading2,
    Link as LinkIcon, Undo, Redo, Code, Pilcrow,
} from 'lucide-react';

const ToolBtn = ({ onClick, active, title, children, testid }) => (
    <button
        type="button"
        onClick={onClick}
        title={title}
        data-testid={testid}
        className={`p-1.5 rounded text-white/70 hover:text-white hover:bg-white/10 transition-colors ${
            active ? 'bg-white/15 text-white' : ''
        }`}
    >
        {children}
    </button>
);

export default function WysiwygEditor({ value, onChange, variables = [], testid = 'wysiwyg-editor' }) {
    const editor = useEditor({
        extensions: [
            StarterKit,
            Link.configure({
                openOnClick: false,
                autolink: true,
                HTMLAttributes: { class: 'text-cyan-300 underline' },
            }),
        ],
        content: value || '',
        editorProps: {
            attributes: {
                class: 'prose prose-invert prose-sm max-w-none focus:outline-none min-h-[280px] px-3 py-2',
                'data-testid': `${testid}-content`,
            },
        },
        onUpdate: ({ editor: ed }) => {
            const html = ed.getHTML();
            if (typeof onChange === 'function') onChange(html);
        },
    });

    // Sync external value updates (when switching templates) without losing focus on every keystroke
    useEffect(() => {
        if (!editor) return;
        const current = editor.getHTML();
        if (value !== current) {
            editor.commands.setContent(value || '', false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [value, editor]);

    const setLink = useCallback(() => {
        if (!editor) return;
        const prev = editor.getAttributes('link').href;
        const url = window.prompt('Enter URL (leave blank to remove)', prev || '');
        if (url === null) return;
        if (url === '') {
            editor.chain().focus().extendMarkRange('link').unsetLink().run();
            return;
        }
        editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
    }, [editor]);

    const insertVar = useCallback((name) => {
        if (!editor) return;
        editor.chain().focus().insertContent(`{{${name}}}`).run();
    }, [editor]);

    if (!editor) {
        return <div className="rounded-lg border border-white/10 bg-black/40 min-h-[280px] animate-pulse" />;
    }

    return (
        <div className="rounded-lg border border-white/10 bg-black/40 overflow-hidden" data-testid={testid}>
            {/* Toolbar */}
            <div className="flex items-center gap-0.5 flex-wrap p-1.5 border-b border-white/10 bg-black/60">
                <ToolBtn testid={`${testid}-bold`} onClick={() => editor.chain().focus().toggleBold().run()}
                    active={editor.isActive('bold')} title="Bold">
                    <Bold className="w-3.5 h-3.5" />
                </ToolBtn>
                <ToolBtn testid={`${testid}-italic`} onClick={() => editor.chain().focus().toggleItalic().run()}
                    active={editor.isActive('italic')} title="Italic">
                    <Italic className="w-3.5 h-3.5" />
                </ToolBtn>
                <ToolBtn testid={`${testid}-code`} onClick={() => editor.chain().focus().toggleCode().run()}
                    active={editor.isActive('code')} title="Inline code">
                    <Code className="w-3.5 h-3.5" />
                </ToolBtn>
                <span className="w-px h-4 bg-white/10 mx-0.5" />
                <ToolBtn testid={`${testid}-h1`} onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
                    active={editor.isActive('heading', { level: 1 })} title="Heading 1">
                    <Heading1 className="w-3.5 h-3.5" />
                </ToolBtn>
                <ToolBtn testid={`${testid}-h2`} onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
                    active={editor.isActive('heading', { level: 2 })} title="Heading 2">
                    <Heading2 className="w-3.5 h-3.5" />
                </ToolBtn>
                <ToolBtn testid={`${testid}-paragraph`} onClick={() => editor.chain().focus().setParagraph().run()}
                    active={editor.isActive('paragraph')} title="Paragraph">
                    <Pilcrow className="w-3.5 h-3.5" />
                </ToolBtn>
                <span className="w-px h-4 bg-white/10 mx-0.5" />
                <ToolBtn testid={`${testid}-bullet-list`} onClick={() => editor.chain().focus().toggleBulletList().run()}
                    active={editor.isActive('bulletList')} title="Bullet list">
                    <List className="w-3.5 h-3.5" />
                </ToolBtn>
                <ToolBtn testid={`${testid}-ordered-list`} onClick={() => editor.chain().focus().toggleOrderedList().run()}
                    active={editor.isActive('orderedList')} title="Numbered list">
                    <ListOrdered className="w-3.5 h-3.5" />
                </ToolBtn>
                <ToolBtn testid={`${testid}-quote`} onClick={() => editor.chain().focus().toggleBlockquote().run()}
                    active={editor.isActive('blockquote')} title="Quote">
                    <Quote className="w-3.5 h-3.5" />
                </ToolBtn>
                <span className="w-px h-4 bg-white/10 mx-0.5" />
                <ToolBtn testid={`${testid}-link`} onClick={setLink} active={editor.isActive('link')} title="Link">
                    <LinkIcon className="w-3.5 h-3.5" />
                </ToolBtn>
                <span className="w-px h-4 bg-white/10 mx-0.5" />
                <ToolBtn testid={`${testid}-undo`} onClick={() => editor.chain().focus().undo().run()} title="Undo">
                    <Undo className="w-3.5 h-3.5" />
                </ToolBtn>
                <ToolBtn testid={`${testid}-redo`} onClick={() => editor.chain().focus().redo().run()} title="Redo">
                    <Redo className="w-3.5 h-3.5" />
                </ToolBtn>
            </div>

            {/* Insert variable bar */}
            {variables.length > 0 && (
                <div className="flex items-center gap-1 flex-wrap p-1.5 border-b border-white/10 bg-black/30">
                    <span className="text-[10px] uppercase tracking-widest text-white/40 mr-1">Insert var:</span>
                    {variables.map((v) => (
                        <Button key={v} variant="outline" size="sm" onClick={() => insertVar(v)}
                            className="h-6 px-2 text-[10px]" data-testid={`${testid}-insert-${v}`}>
                            {`{{${v}}}`}
                        </Button>
                    ))}
                </div>
            )}

            <EditorContent editor={editor} />
        </div>
    );
}
