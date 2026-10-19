import QtQuick
import Quickshell
import Quickshell.Io

// An invisible Item owns the Process children; it has no visual surface.
Item {
    id: root
    visible: false

    property var messages: []
    property string connectionState: "disconnected"
    property string statusText: "Choose a local token file and explicitly consent to read-only history."
    property string modelLabel: "Gentle Dot"
    property bool streaming: false
    property bool canSend: false
    property bool canStop: false
    property string endpoint: ""
    property string tokenFile: ""
    property bool consent: false
    property bool awaitingNode: false
    property bool awaitingBridge: false

    readonly property string trustedPath: Quickshell.env("PATH") || "/usr/bin:/bin"
    readonly property string helperPath: decodeURIComponent(Qt.resolvedUrl("scripts/backend_bridge.mjs").toString().replace(/^file:\/\//, ""))

    function validEndpoint(value) {
        return /^ws:\/\/(127\.0\.0\.1|\[::1\]):[1-9][0-9]{0,4}\/ws$/.test(String(value || ""))
    }
    function validFile(value) { return String(value || "").startsWith("/") }
    function resetMetadata() { endpoint = ""; tokenFile = ""; consent = false }
    function fail(message) {
        connectionState = "error"
        statusText = message
        awaitingNode = false
        awaitingBridge = false
    }
    function connect(url, filePath, approved) {
        if (nodeCheck.running || bridge.running) return
        if (approved !== true || !validEndpoint(url) || !validFile(filePath)) {
            fail("Choose a loopback endpoint, an absolute token file, and confirm consent.")
            return
        }
        endpoint = String(url)
        tokenFile = String(filePath)
        consent = true
        connectionState = "connecting"
        statusText = "Checking the local read-only bridge…"
        awaitingNode = true
        nodeCheck.running = true
    }
    function disconnect() {
        // Mark intentional termination first: a queued bridge command could wait for history.
        awaitingNode = false
        awaitingBridge = false
        if (nodeCheck.running) nodeCheck.running = false
        if (bridge.running) bridge.running = false
        resetMetadata()
        connectionState = "disconnected"
        statusText = "Disconnected. No local pairing details are retained."
        modelLabel = "Gentle Dot"
    }
    function send(text) {}
    function abort() {}
    function startBridge() {
        if (!consent || !endpoint || !tokenFile) return
        awaitingBridge = true
        bridge.running = true
    }
    function parseLine(line) {
        var value
        try { value = JSON.parse(line) } catch (_) { return }
        if (!value || typeof value !== "object") return
        if (value.type === "status" && (value.state === "connected" || value.state === "disconnected")) {
            connectionState = value.state
            if (value.state === "connected") {
                modelLabel = typeof value.modelLabel === "string" && value.modelLabel.length <= 256 ? value.modelLabel : "Gentle Dot"
                statusText = "Connected for read-only history. Sending is not available yet."
                bridge.write(JSON.stringify({ command: "history" }) + "\n")
            } else if (connectionState === "disconnected") {
                statusText = "Disconnected."
            }
        } else if (value.type === "history" && Array.isArray(value.history)) {
            var normalized = []
            for (var i = 0; i < value.history.length && i < 100; i++) {
                var entry = value.history[i]
                if (entry && typeof entry.id === "string" && (entry.role === "user" || entry.role === "assistant") && typeof entry.text === "string")
                    normalized.push({ id: entry.id.slice(0, 256), role: entry.role, text: entry.text.slice(0, 16384) })
            }
            messages = normalized
            statusText = normalized.length === 0 ? "No history in this shared session." : "Read-only shared-session history. Sending is not available yet."
        } else if (value.type === "error") {
            fail("Connection unavailable. Open Gentle Dot for the full app.")
        }
    }

    Process {
        id: nodeCheck
        running: false
        clearEnvironment: true
        environment: ({ "PATH": root.trustedPath, "LANG": "C.UTF-8" })
        command: ["/usr/bin/env", "-i", "PATH=" + root.trustedPath, "LANG=C.UTF-8", "node", "--version"]
        stdout: SplitParser {
            splitMarker: "\n"
            onRead: function(data) {
                if (/^v(?:2[4-9]|[3-9][0-9])\./.test(String(data).trim())) root.awaitingNode = false
            }
        }
        onExited: function(exitCode) {
            if (!root.consent) return
            if (exitCode === 0 && !root.awaitingNode) root.startBridge()
            else root.fail("Node 24+ is required for local read-only history. Open Gentle Dot for the full app.")
        }
    }

    Process {
        id: bridge
        running: false
        stdinEnabled: true
        clearEnvironment: true
        environment: ({ "PATH": root.trustedPath, "LANG": "C.UTF-8" })
        command: ["/usr/bin/env", "-i", "PATH=" + root.trustedPath, "LANG=C.UTF-8", "node", root.helperPath]
        onStarted: write(JSON.stringify({ command: "connect", consent: true, url: root.endpoint, tokenFile: root.tokenFile }) + "\n")
        stdout: SplitParser { splitMarker: "\n"; onRead: function(data) { root.parseLine(data) } }
        onExited: function() {
            var unexpected = root.awaitingBridge && (root.connectionState === "connecting" || root.connectionState === "connected")
            root.awaitingBridge = false
            if (unexpected) root.fail("Connection unavailable. Open Gentle Dot for the full app.")
        }
    }

    Component.onDestruction: disconnect()
}
