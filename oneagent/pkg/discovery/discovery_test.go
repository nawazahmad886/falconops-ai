package discovery

import "testing"

func TestClassifyRuntime(t *testing.T) {
	cases := []struct {
		cmdline string
		want    string
	}{
		{"node /app/server.js", "nodejs"},
		{"nodejs index.js", "nodejs"},
		{"python3 manage.py runserver", "python"},
		{"java -Xmx512m -jar payments-service.jar", "java"},
		{"dotnet /srv/Checkout.Api.dll", "dotnet"},
		{"/usr/local/bin/order-service --port 8080", "native"},
		{"bash -c sleep 5", ""},
	}
	for _, c := range cases {
		if got := ClassifyRuntime(c.cmdline); got != c.want {
			t.Errorf("ClassifyRuntime(%q) = %q, want %q", c.cmdline, got, c.want)
		}
	}
}

func TestDeriveServiceName(t *testing.T) {
	cases := []struct {
		cmdline, runtime, cwd, want string
	}{
		{"java -jar payments-service.jar", "java", "", "payments-service"},
		{"node server.js", "nodejs", "/srv/checkout-api", "checkout-api"},
		{"node index.js", "nodejs", "/srv/checkout-api", "checkout-api"},
		{"python3 app.py", "python", "/opt/billing", "billing"},
		{"python3 worker.py", "python", "/opt/billing", "worker"},
		{"dotnet /srv/Checkout.Api.dll", "dotnet", "", "checkout.api"},
		{"node --service-name=payments index.js", "nodejs", "/x", "payments"},
	}
	for _, c := range cases {
		if got := DeriveServiceName(c.cmdline, c.runtime, c.cwd); got != c.want {
			t.Errorf("DeriveServiceName(%q) = %q, want %q", c.cmdline, got, c.want)
		}
	}
}
