import QtQuick
import Quickshell
import "plugin" as Plugin

ShellRoot {
    id: shell
    property int failures: 0
    property string endpoint: Quickshell.env("GENTLE_PAIR_URL") || ""
    property string tokenPath: Quickshell.env("GENTLE_PAIR_TOKEN") || ""

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
    function check(condition, message) { if (!condition) { failures++; console.error("T18_FAIL " + message) } }
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
        interval: 1800; running: true; repeat: false
        onTriggered: {
            check(controller.connectionState === "connected", "write controls: explicit pairing did not connect")
            check(controller.messages.length === 2 && controller.messages[0].text.indexOf("[redacted]") >= 0, "write controls: history was not normalized")
            // Write consent toggle should be visible when connected
            check(pairing.verificationWriteConsent.visible === true, "write controls: write consent toggle not visible when connected")
            check(pairing.verificationWriteConsent.checked === false, "write controls: write consent toggle should start unchecked")
            check(controller.writeWanted === false, "write controls: controller writeWanted should start false")
            check(controller.writeGranted === false, "write controls: controller writeGranted should start false")
            check(controller.canSend === false, "write controls: controller canSend should start false")
            // Enable write access
            pairing.verificationWriteConsent.clicked()
            check(pairing.verificationWriteConsent.checked === true, "write controls: write consent toggle not checked after click")
            check(controller.writeWanted === true, "write controls: controller writeWanted not true after toggle")
            check(controller.writeGranted === false, "write controls: writeGranted should still be false (awaiting bridge response)")
            check(controller.canSend === false, "write controls: canSend should still be false (awaiting grant)")
            // Simulate bridge granting write access by injecting a write_access response
            controller.parseLine('{"type":"write_access","enabled":true}')
            check(controller.writeGranted === true, "write controls: writeGranted not true after bridge grant")
            check(controller.canSend === true, "write controls: canSend not true after grant")
            check(controller.canStop === true, "write controls: canStop not true after grant")
            // Send a message
            var sendResult = controller.send("test message")
            check(sendResult === true, "write controls: send() returned false when it should succeed")
            // Request stop
            controller.requestStop()
            check(controller.pendingStop === true, "write controls: pendingStop not true after requestStop")
            check(pairing.verificationConfirmStop.visible === true, "write controls: confirm stop button not visible")
            check(pairing.verificationCancelStop.visible === true, "write controls: cancel stop button not visible")
            // Cancel stop
            controller.cancelStop()
            check(controller.pendingStop === false, "write controls: pendingStop not false after cancelStop")
            check(pairing.verificationConfirmStop.visible === false, "write controls: confirm stop button still visible after cancel")
            // Request stop again and confirm
            controller.requestStop()
            check(controller.pendingStop === true, "write controls: pendingStop not true after second requestStop")
            // Simulate bridge receiving abort (we can't easily test the bridge write, but we can test abort())
            var abortResult = controller.abort(true)
            check(abortResult === true, "write controls: abort(true) returned false when it should succeed")
            check(controller.pendingStop === false, "write controls: pendingStop not false after abort")
            // Disable write access
            pairing.verificationWriteConsent.clicked()
            check(pairing.verificationWriteConsent.checked === false, "write controls: write consent toggle not unchecked after second click")
            check(controller.writeWanted === false, "write controls: controller writeWanted not false after toggle off")
            check(controller.writeGranted === false, "write controls: controller writeGranted not false after toggle off")
            check(controller.canSend === false, "write controls: controller canSend not false after toggle off")
            check(controller.canStop === false, "write controls: controller canStop not false after toggle off")
            // Disconnect and verify cleanup
            pairing.verificationDisconnect.clicked()
            check(!pairing.accepted && !pairing.verificationToggle.checked && pairing.verificationToken.text === "" && pairing.verificationEndpoint.text === "ws://127.0.0.1:4317/ws", "write controls: disconnect retained form pairing state")
            check(controller.connectionState === "disconnected" && controller.endpoint === "" && controller.tokenFile === "" && !controller.consent, "write controls: disconnect did not clear controller metadata")
            check(controller.writeWanted === false && controller.writeGranted === false && controller.pendingStop === false, "write controls: write state not cleared on disconnect")
            console.log("T18_RESULT failures=" + failures)
            Qt.exit(failures === 0 ? 0 : 1)
        }
    }
}