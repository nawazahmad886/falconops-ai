import React, { useState, useMemo } from 'react';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs';
import { toast } from 'sonner';
import {
    Cpu, Copy, CheckCircle2, ExternalLink, Terminal, Zap, Activity, BookOpen, Server,
} from 'lucide-react';
import AnimatedTerminal from '../components/AnimatedTerminal';

const API = process.env.REACT_APP_BACKEND_URL || '';
const ENDPOINT = `${API}/api/otel`;
const TRACES_ENDPOINT = `${API}/api/otel/v1/traces`;

const SNIPPETS = {
    python: {
        title: 'Python (FastAPI / Flask / Django)',
        icon: '🐍',
        install: `pip install opentelemetry-distro opentelemetry-exporter-otlp
opentelemetry-bootstrap -a install`,
        env: `# Configure agent to ship traces to FalconOps
export OTEL_SERVICE_NAME=my-python-service
export OTEL_EXPORTER_OTLP_ENDPOINT=${ENDPOINT}
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_TRACES_EXPORTER=otlp`,
        run: `# Auto-instrument any Python app:
opentelemetry-instrument --traces_exporter otlp \\
  --exporter_otlp_endpoint ${ENDPOINT} \\
  --service_name my-python-service \\
  python app.py

# Or, for FastAPI/uvicorn:
opentelemetry-instrument uvicorn main:app --host 0.0.0.0 --port 8000`,
    },
    node: {
        title: 'Node.js (Express / NestJS / Next.js)',
        icon: '🟢',
        install: `npm install --save \\
  @opentelemetry/sdk-node \\
  @opentelemetry/auto-instrumentations-node \\
  @opentelemetry/exporter-trace-otlp-http`,
        env: `// tracing.js — load before your app
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-http');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');

const sdk = new NodeSDK({
  serviceName: 'my-node-service',
  traceExporter: new OTLPTraceExporter({
    url: '${TRACES_ENDPOINT}',
  }),
  instrumentations: [getNodeAutoInstrumentations()],
});
sdk.start();`,
        run: `# Start your Node app with tracing pre-loaded
node --require ./tracing.js server.js`,
    },
    java: {
        title: 'Java (Spring Boot / Quarkus / Micronaut)',
        icon: '☕',
        install: `# Download the OpenTelemetry Java agent
curl -L -o opentelemetry-javaagent.jar \\
  https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/latest/download/opentelemetry-javaagent.jar`,
        env: `# Set environment variables
export OTEL_SERVICE_NAME=my-java-service
export OTEL_EXPORTER_OTLP_ENDPOINT=${ENDPOINT}
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_TRACES_EXPORTER=otlp`,
        run: `# Run any Spring Boot / java -jar app with the agent
java -javaagent:./opentelemetry-javaagent.jar \\
     -Dotel.service.name=my-java-service \\
     -Dotel.exporter.otlp.endpoint=${ENDPOINT} \\
     -jar app.jar`,
    },
    go: {
        title: 'Go (Gin / Echo / net/http)',
        icon: '🦫',
        install: `go get \\
  go.opentelemetry.io/otel \\
  go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp \\
  go.opentelemetry.io/otel/sdk/trace`,
        env: `// main.go — initialise tracer
import (
    "context"
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
    sdktrace "go.opentelemetry.io/otel/sdk/trace"
    "go.opentelemetry.io/otel/sdk/resource"
    semconv "go.opentelemetry.io/otel/semconv/v1.21.0"
)

func initTracer(ctx context.Context) (*sdktrace.TracerProvider, error) {
    exp, err := otlptracehttp.New(ctx,
        otlptracehttp.WithEndpoint("${API.replace(/^https?:\/\//, '')}"),
        otlptracehttp.WithURLPath("/api/otel/v1/traces"),
    )
    if err != nil { return nil, err }

    tp := sdktrace.NewTracerProvider(
        sdktrace.WithBatcher(exp),
        sdktrace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName("my-go-service"),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp, nil
}`,
        run: `# Run your Go service — tracing now active
go run main.go`,
    },
    curl: {
        title: 'Raw OTLP/HTTP (cURL test)',
        icon: '🧪',
        install: `# No SDK required — just push OTLP/HTTP JSON directly`,
        env: `# Sample payload mimicking an OpenTelemetry SDK exporter
cat > /tmp/trace.json <<'EOF'
{
  "resourceSpans": [{
    "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "demo-svc"}}]},
    "scopeSpans": [{
      "scope": {"name": "manual"},
      "spans": [{
        "traceId": "abc1234567890abc1234567890abc12",
        "spanId":  "1111111122222222",
        "name":    "GET /api/health",
        "kind":    2,
        "startTimeUnixNano": "1739808000000000000",
        "endTimeUnixNano":   "1739808000150000000",
        "status": {"code": 1}
      }]
    }]
  }]
}
EOF`,
        run: `curl -X POST ${TRACES_ENDPOINT} \\
  -H "Content-Type: application/json" \\
  --data @/tmp/trace.json
# Expected: {"accepted": 1}`,
    },
};

const Snippet = ({ code, label, testid }) => {
    const [copied, setCopied] = useState(false);
    const copy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        toast.success(`${label} copied`);
        setTimeout(() => setCopied(false), 2000);
    };
    return (
        <div className="relative group">
            <pre
                className="text-[12px] text-white/85 font-mono bg-black/60 border border-white/10 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap break-words"
                data-testid={`snippet-${testid}`}
            >
                {code}
            </pre>
            <Button
                size="sm"
                variant="outline"
                onClick={copy}
                className="absolute top-2 right-2 h-7 px-2 text-[10px] opacity-70 group-hover:opacity-100"
                data-testid={`copy-${testid}`}
            >
                {copied ? <CheckCircle2 className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
                <span className="ml-1">{copied ? 'Copied' : 'Copy'}</span>
            </Button>
        </div>
    );
};

const Step = ({ n, title, children }) => (
    <div className="space-y-2">
        <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 text-[11px] font-semibold flex items-center justify-center">{n}</span>
            <span className="text-sm font-semibold text-white">{title}</span>
        </div>
        {children}
    </div>
);

export default function APMQuickstartPage() {
    const [tab, setTab] = useState('python');
    const langs = useMemo(() => Object.keys(SNIPPETS), []);

    const demoLines = useMemo(() => ([
        { prompt: '$', text: 'pip install opentelemetry-distro opentelemetry-exporter-otlp', classify: 'cmd' },
        { prompt: '',  text: 'Successfully installed opentelemetry-distro opentelemetry-exporter-otlp', classify: 'log' },
        { prompt: '$', text: 'export OTEL_SERVICE_NAME=payment-service', classify: 'cmd' },
        { prompt: '$', text: `export OTEL_EXPORTER_OTLP_ENDPOINT=${ENDPOINT}`, classify: 'cmd' },
        { prompt: '$', text: 'opentelemetry-instrument uvicorn main:app --host 0.0.0.0 --port 8000', classify: 'cmd' },
        { prompt: '',  text: 'INFO:     Uvicorn running on http://0.0.0.0:8000', classify: 'log' },
        { prompt: '',  text: 'INFO:     OTLP exporter initialized → ' + ENDPOINT, classify: 'info' },
        { prompt: '',  text: 'INFO:     Span POST /pay/charge sent — trace_id=4e8a…3b', classify: 'log' },
        { prompt: '',  text: 'INFO:     Span GET  /pay/status sent — trace_id=4e8a…3b', classify: 'log' },
        { prompt: '',  text: 'FalconOps APM received 2 spans · 0 errors · root: payment-service.charge', classify: 'ok', pauseAfterMs: 1400 },
    ]), []);

    return (
        <div className="p-6 space-y-6 max-w-6xl" data-testid="apm-quickstart-page">
            <div>
                <h1 className="text-2xl font-semibold text-white flex items-center gap-2">
                    <Cpu className="w-6 h-6 text-cyan-400" />
                    APM Quickstart
                </h1>
                <p className="text-sm text-white/55 mt-1">
                    Start sending OpenTelemetry traces to FalconOps in under 2 minutes. Pick your language and copy-paste.
                </p>
            </div>

            {/* Animated hero terminal — 'live' demo */}
            <div className="grid lg:grid-cols-5 gap-4 items-stretch">
                <Card className="lg:col-span-3 bg-black/0 border-0 shadow-none">
                    <AnimatedTerminal lines={demoLines} />
                </Card>
                <Card className="lg:col-span-2 bg-gradient-to-br from-cyan-500/[0.06] via-black/40 to-black/40 border-cyan-500/30">
                    <CardContent className="p-5 space-y-3">
                        <div className="flex items-center gap-2">
                            <Zap className="w-4 h-4 text-cyan-400" />
                            <span className="text-xs uppercase tracking-widest text-cyan-300 font-semibold">2-Minute Setup</span>
                        </div>
                        <ul className="space-y-2 text-[13px] text-white/75">
                            <li className="flex items-start gap-2">
                                <span className="w-5 h-5 rounded-full bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-[10px] font-semibold flex items-center justify-center shrink-0">1</span>
                                Install the OTel SDK <span className="text-white/40">(one line)</span>
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="w-5 h-5 rounded-full bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-[10px] font-semibold flex items-center justify-center shrink-0">2</span>
                                Point <code className="text-white/80 text-[11px]">OTEL_EXPORTER_OTLP_ENDPOINT</code> at FalconOps
                            </li>
                            <li className="flex items-start gap-2">
                                <span className="w-5 h-5 rounded-full bg-cyan-500/15 border border-cyan-500/30 text-cyan-300 text-[10px] font-semibold flex items-center justify-center shrink-0">3</span>
                                Run your app — traces stream in real-time
                            </li>
                            <li className="flex items-start gap-2">
                                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
                                <span className="text-emerald-300">Visible in <a href="/apm-traces" className="underline">APM Traces</a> within seconds</span>
                            </li>
                        </ul>
                    </CardContent>
                </Card>
            </div>

            {/* Endpoint card */}
            <Card className="bg-gradient-to-br from-cyan-500/[0.06] via-black/40 to-black/40 border-cyan-500/30">
                <CardContent className="p-5 space-y-3">
                    <div className="flex items-center gap-2">
                        <Zap className="w-4 h-4 text-cyan-400" />
                        <span className="text-xs uppercase tracking-widest text-cyan-300 font-semibold">Your OTLP Endpoint</span>
                        <Badge className="text-[10px] bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">Live</Badge>
                    </div>
                    <Snippet code={ENDPOINT} label="OTLP base endpoint" testid="endpoint-base" />
                    <div className="text-[11px] text-white/50">
                        Used as <code className="text-white/70">OTEL_EXPORTER_OTLP_ENDPOINT</code>. The agent will append <code>/v1/traces</code>, <code>/v1/metrics</code>, and <code>/v1/logs</code> automatically.
                    </div>
                    <div className="flex items-center gap-2 pt-1">
                        <Server className="w-3.5 h-3.5 text-white/40" />
                        <span className="text-[11px] text-white/60">Direct trace POST URL:</span>
                        <code className="text-[11px] text-cyan-300">{TRACES_ENDPOINT}</code>
                    </div>
                </CardContent>
            </Card>

            {/* Language tabs */}
            <Card className="bg-black/40 border-white/10">
                <CardContent className="p-5">
                    <Tabs value={tab} onValueChange={setTab}>
                        <TabsList className="bg-black/40 border border-white/10" data-testid="quickstart-langs">
                            {langs.map((k) => (
                                <TabsTrigger key={k} value={k} data-testid={`lang-${k}`}>
                                    <span className="mr-1.5">{SNIPPETS[k].icon}</span>
                                    {SNIPPETS[k].title.split(' ')[0]}
                                </TabsTrigger>
                            ))}
                        </TabsList>
                        {langs.map((k) => {
                            const s = SNIPPETS[k];
                            return (
                                <TabsContent key={k} value={k} className="mt-5 space-y-5" data-testid={`pane-${k}`}>
                                    <div className="text-sm font-semibold text-white">{s.title}</div>
                                    <Step n={1} title="Install the OpenTelemetry SDK / Agent">
                                        <Snippet code={s.install} label="Install command" testid={`${k}-install`} />
                                    </Step>
                                    <Step n={2} title="Configure the exporter">
                                        <Snippet code={s.env} label="Configuration" testid={`${k}-env`} />
                                    </Step>
                                    <Step n={3} title="Run your service">
                                        <Snippet code={s.run} label="Run command" testid={`${k}-run`} />
                                    </Step>
                                </TabsContent>
                            );
                        })}
                    </Tabs>
                </CardContent>
            </Card>

            {/* Verify */}
            <Card className="bg-black/40 border-white/10">
                <CardContent className="p-5 space-y-3">
                    <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                        <span className="text-sm font-semibold text-white">Verify ingestion</span>
                    </div>
                    <p className="text-[12px] text-white/60 leading-relaxed">
                        Once your app starts and serves a request, traces appear in the <strong>APM Traces</strong> page within seconds.
                    </p>
                    <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" asChild data-testid="open-traces-btn">
                            <a href="/apm-traces">
                                <Activity className="w-4 h-4 mr-1.5" /> Open APM Traces
                            </a>
                        </Button>
                        <Button variant="outline" size="sm" asChild data-testid="otel-docs-link">
                            <a href="https://opentelemetry.io/docs/instrumentation/" target="_blank" rel="noreferrer">
                                <BookOpen className="w-4 h-4 mr-1.5" /> OpenTelemetry Docs
                                <ExternalLink className="w-3 h-3 ml-1.5" />
                            </a>
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Troubleshoot */}
            <Card className="bg-black/40 border-white/10">
                <CardContent className="p-5 space-y-3">
                    <div className="flex items-center gap-2">
                        <Terminal className="w-4 h-4 text-amber-400" />
                        <span className="text-sm font-semibold text-white">Troubleshooting</span>
                    </div>
                    <ul className="text-[12px] text-white/65 space-y-2 list-disc pl-5">
                        <li><strong>Connection refused / DNS error:</strong> ensure the agent can reach <code>{API}</code> from the runtime host.</li>
                        <li><strong>Traces not visible:</strong> the time range selector defaults to 24h — widen to 7d/30d if your traces have older app-side timestamps.</li>
                        <li><strong>Empty service name:</strong> set <code>OTEL_SERVICE_NAME</code> or <code>service.name</code> resource attribute.</li>
                        <li><strong>Auth:</strong> the OTLP endpoint accepts unauthenticated POSTs (designed for in-cluster agents). Restrict externally via firewall / API gateway as needed.</li>
                    </ul>
                </CardContent>
            </Card>
        </div>
    );
}
