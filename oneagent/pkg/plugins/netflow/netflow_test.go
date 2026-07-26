package netflow

import (
	"net"
	"os"
	"path/filepath"
	"testing"
)

func TestDecodeProcAddrIPv4(t *testing.T) {
	ip, err := decodeProcAddr("0100007F")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ip.Equal(net.ParseIP("127.0.0.1")) {
		t.Errorf("got %v, want 127.0.0.1", ip)
	}
}

func TestDecodeProcAddrIPv4MappedIPv6(t *testing.T) {
	// ::ffff:127.0.0.1 -- a commonly-cited real /proc/net/tcp6 example.
	ip, err := decodeProcAddr("0000000000000000FFFF00000100007F")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ip.Equal(net.ParseIP("127.0.0.1")) {
		t.Errorf("got %v, want 127.0.0.1 (IPv4-mapped)", ip)
	}
}

func TestDecodeProcAddrIPv6Loopback(t *testing.T) {
	// ::1 encoded as four 8-char (4-byte) groups, each byte-reversed:
	// group1=00000000, group2=00000000, group3=00000000, group4=01000000
	// (group4's raw bytes [00,00,00,01] reversed -> file hex "01000000").
	ip, err := decodeProcAddr("0000000000000000" + "0000000001000000")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ip.Equal(net.ParseIP("::1")) {
		t.Errorf("got %v, want ::1", ip)
	}
}

func TestDecodeProcAddrInvalid(t *testing.T) {
	if _, err := decodeProcAddr("not-hex"); err == nil {
		t.Error("expected error for non-hex input")
	}
	if _, err := decodeProcAddr("0102"); err == nil {
		t.Error("expected error for wrong-length input (2 bytes)")
	}
	if _, err := decodeProcAddr("000000000000000000000000000000000102"); err == nil {
		t.Error("expected error for wrong-length input (19 bytes)")
	}
}

func TestSplitProcAddrPort(t *testing.T) {
	ip, port, err := splitProcAddrPort("0100007F:0050")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ip.Equal(net.ParseIP("127.0.0.1")) || port != 80 {
		t.Errorf("got %v:%d, want 127.0.0.1:80", ip, port)
	}

	ip, port, err = splitProcAddrPort("00000000000000000000000001000000:1F90")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !ip.Equal(net.ParseIP("::1")) || port != 8080 {
		t.Errorf("got %v:%d, want ::1:8080", ip, port)
	}

	if _, _, err := splitProcAddrPort("no-colon-here"); err == nil {
		t.Error("expected error for missing ':' separator")
	}
	if _, _, err := splitProcAddrPort("0100007F:zzzz"); err == nil {
		t.Error("expected error for non-hex port")
	}
}

func TestParseConnections(t *testing.T) {
	dir := t.TempDir()
	if err := os.MkdirAll(filepath.Join(dir, "net"), 0o755); err != nil {
		t.Fatal(err)
	}

	// Header line + one ESTABLISHED connection (127.0.0.1:80 -> 8.8.8.8:443)
	// remote 8.8.8.8 = 08080808 hex; local 127.0.0.1:80 = 0100007F:0050.
	tcpContent := "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n" +
		"   0: 0100007F:0050 08080808:01BB 01 00000000:00000000 00:00000000 00000000     0        0 12345 1 0000000000000000 20 4 30 10 -1\n" +
		"   1: 0100007F:0051 09090909:01BB 06 00000000:00000000 00:00000000 00000000     0        0 12346 1 0000000000000000 20 4 30 10 -1\n" +
		"malformed line with too few fields\n"

	if err := os.WriteFile(filepath.Join(dir, "net", "tcp"), []byte(tcpContent), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "net", "tcp6"), []byte(""), 0o644); err != nil {
		t.Fatal(err)
	}

	p := &Plugin{procRoot: dir}
	conns := p.parseConnections()

	if len(conns) != 2 {
		t.Fatalf("got %d connections, want 2 (malformed line must be skipped without panic)", len(conns))
	}

	established := conns[0]
	if established.LocalIP != "127.0.0.1" || established.LocalPort != 80 {
		t.Errorf("local = %s:%d, want 127.0.0.1:80", established.LocalIP, established.LocalPort)
	}
	if established.RemoteIP != "8.8.8.8" || established.RemotePort != 443 {
		t.Errorf("remote = %s:%d, want 8.8.8.8:443", established.RemoteIP, established.RemotePort)
	}
	if established.State != establishedState {
		t.Errorf("state = %s, want %s", established.State, establishedState)
	}
	if established.Inode != "12345" {
		t.Errorf("inode = %s, want 12345", established.Inode)
	}

	if conns[1].State != "06" {
		t.Errorf("second connection state = %s, want 06 (TIME_WAIT)", conns[1].State)
	}
}

func TestParseConnectionsMissingFiles(t *testing.T) {
	p := &Plugin{procRoot: t.TempDir()}
	conns := p.parseConnections()
	if len(conns) != 0 {
		t.Errorf("got %d connections from an empty proc root, want 0 (must not panic)", len(conns))
	}
}

func TestBuildInodeToPIDMap(t *testing.T) {
	dir := t.TempDir()

	// PID 100: two fds, one is a socket (inode 555), one is a regular file.
	pid100Fd := filepath.Join(dir, "100", "fd")
	if err := os.MkdirAll(pid100Fd, 0o755); err != nil {
		t.Fatal(err)
	}
	mustSymlink(t, "socket:[555]", filepath.Join(pid100Fd, "3"))
	mustSymlink(t, "/var/log/app.log", filepath.Join(pid100Fd, "4"))

	// PID 200: one socket fd (inode 777).
	pid200Fd := filepath.Join(dir, "200", "fd")
	if err := os.MkdirAll(pid200Fd, 0o755); err != nil {
		t.Fatal(err)
	}
	mustSymlink(t, "socket:[777]", filepath.Join(pid200Fd, "5"))

	// Non-PID directory must be ignored.
	if err := os.MkdirAll(filepath.Join(dir, "net"), 0o755); err != nil {
		t.Fatal(err)
	}

	p := &Plugin{procRoot: dir}
	m := p.buildInodeToPIDMap()

	if m["555"] != 100 {
		t.Errorf("inode 555 -> pid %d, want 100", m["555"])
	}
	if m["777"] != 200 {
		t.Errorf("inode 777 -> pid %d, want 200", m["777"])
	}
	if len(m) != 2 {
		t.Errorf("got %d entries, want 2 (non-socket fd and non-PID dir must be excluded)", len(m))
	}
}

func mustSymlink(t *testing.T, target, link string) {
	t.Helper()
	if err := os.Symlink(target, link); err != nil {
		t.Fatalf("symlink %s -> %s: %v", link, target, err)
	}
}
