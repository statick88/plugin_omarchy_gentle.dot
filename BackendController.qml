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
    property bool writeWanted: false
    property bool writeGranted: false
    property bool pendingStop: false

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
        writeWanted = false; writeGranted = false; pendingStop = false; streaming = false; canSend = false; canStop = false
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
    function setWrite(enabled) {
        writeWanted = enabled === true; writeGranted = false; pendingStop = false
        gateWrite()
        if (bridge.running && connectionState === "connected") {
            var payload = { command: "write_access", enabled: writeWanted }
            if (writeWanted) payload.consent = true
            bridge.write(JSON.stringify(payload) + "\n")
        }
    }
    function send(text) {
        var value = String(text || "")
        if (!canSend || !value.trim() || JSON.stringify({ command: "send", text: value, consent: true }).length > 16384) return false
        bridge.write(JSON.stringify({ command: "send", text: value, consent: true }) + "\n"); return true
    }
    function abort(confirmed) {
        if (confirmed !== true || !pendingStop || !canStop) return false
        pendingStop = false; bridge.write(JSON.stringify({ command: "abort", confirmed: true }) + "\n"); return true
    }
    function requestStop() { if (canStop) pendingStop = true }
    function cancelStop() { pendingStop = false }
    function gateWrite() { canSend = writeWanted && writeGranted && connectionState === "connected"; canStop = canSend }
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
                statusText = "Connected for read-only history."
                gateWrite(); bridge.write(JSON.stringify({ command: "history" }) + "\n")
            } else if (connectionState === "disconnected") {
                statusText = "Disconnected."
            }
        } else if (value.type === "write_access") {
            writeGranted = value.enabled === true && writeWanted && connectionState === "connected"; gateWrite()
        } else if (value.type === "stream") {
            var id = typeof value.messageId === "string" ? value.messageId.slice(0, 256) : ""
            if (id && (value.event === "user_message" || value.event === "message_delta" || value.event === "message_done")) {
                var rows = messages.slice(); var index = rows.findIndex(function(row) { return row.id === id })
                var prior = index >= 0 ? rows[index] : { id: id, role: value.event === "user_message" ? "user" : "assistant", text: "" }
                var text = value.event === "message_delta" ? prior.text + String(value.delta || "") : String(value.text || "")
                if (text.length <= 16384) { prior.text = text; if (index >= 0) rows[index] = prior; else if (rows.length < 100) rows.push(prior); messages = rows }
                streaming = value.event === "message_delta"; if (value.event === "message_done") streaming = false
            }
        } else if (value.type === "agent_state") {
            statusText = "Shared session: " + String(value.state || "idle")
        } else if (value.type === "action_required" || value.type === "model_error") {
            statusText = "Use the full Gentle Dot app for this action."
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
            gateWrite()
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
