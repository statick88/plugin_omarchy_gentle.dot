import QtQuick
import Quickshell
import "plugin" as Plugin

ShellRoot {
    id: shell
    property int failures: 0
    property string endpoint: Quickshell.env("GENTLE_PAIR_URL") || ""
    property string tokenPath: Quickshell.env("GENTLE_PAIR_TOKEN") || ""
    property bool bridgeExit: Quickshell.env("GENTLE_BRIDGE_EXIT") === "1"

    QtObject {
        id: fakeBar
        property string position: "top"
        property int barSize: 28
        property string fontFamily: "synthetic-monospace"
        property color barForeground: "#d8d0d5"
        function requestPopout(owner) {}
        function releasePopout(owner) {}
    }
    Plugin.BackendController { id: controller }
    PanelWindow {
        visible: true; implicitWidth: 640; implicitHeight: 28; color: "transparent"
        anchors { top: true; left: true; right: true }
        Item { id: anchor; x: 300; y: 2; width: 28; height: 24 }
        Plugin.Panel { id: popup; anchorItem: anchor; bar: fakeBar; chatController: controller }
    }
    function check(condition, message) { if (!condition) { failures++; console.error("T17_FAIL " + message) } }
    function find(root, name) {
        if (root && typeof root.findChild === "function") {
            var direct = root.findChild(name)
            if (direct) return direct
        }
        if (root && root.objectName === name) return root
        var children = root && root.children ? root.children : []
        for (var i = 0; i < children.length; i++) {
            var found = find(children[i], name)
            if (found) return found
        }
        if (root && root.contentItem) return find(root.contentItem, name)
        return null
    }
    property var form: null
    property var endpointField: null
    property var tokenField: null
    property var consentToggle: null
    property var connectButton: null
    property var disconnectButton: null
    property var pairing: null
    Timer {
        interval: 500; running: true; repeat: false
        onTriggered: {
            popup.open(); pairing = popup.verificationPairing
            pairing.verificationEndpoint.text = endpoint
            pairing.verificationToken.text = tokenPath
            pairing.verificationToggle.clicked()
            pairing.verificationConnect.clicked()
        }
    }
    Timer {
        interval: bridgeExit ? 1200 : 1800; running: true; repeat: false
        onTriggered: {
            if (bridgeExit) {
                check(controller.connectionState === "error", "abrupt owned bridge exit left connected state")
                check(controller.statusText === "Connection unavailable. Open Gentle Dot for the full app.", "bridge exit was not generic")
                console.log("T17_RESULT failures=" + failures)
                Qt.exit(failures === 0 ? 0 : 1)
                return
            }
            check(controller.connectionState === "connected", "explicit pairing did not connect")
            check(controller.messages.length === 2 && controller.messages[0].text.indexOf("[redacted]") >= 0, "history was not normalized")
            pairing.verificationDisconnect.clicked()
            check(!pairing.accepted && !pairing.verificationToggle.checked && pairing.verificationToken.text === "" && pairing.verificationEndpoint.text === "ws://127.0.0.1:4317/ws", "disconnect retained form pairing state")
            check(controller.connectionState === "disconnected" && controller.endpoint === "" && controller.tokenFile === "" && !controller.consent, "disconnect did not clear controller metadata")
        }
    }
    Timer {
        interval: 2100; running: !bridgeExit; repeat: false
        onTriggered: {
            check(controller.connectionState === "disconnected", "intentional owned-child exit changed disconnect state")
            pairing.verificationConnect.clicked()
            check(controller.connectionState === "error", "connect without renewed consent was not refused")
            console.log("T17_RESULT failures=" + failures)
            Qt.exit(failures === 0 ? 0 : 1)
        }
    }
}
