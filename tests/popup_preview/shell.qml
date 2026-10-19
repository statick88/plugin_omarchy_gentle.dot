import QtQuick
import Quickshell
import "plugin" as Plugin

ShellRoot {
  id: shell

  property int nativeOpenCount: 0
  property int failures: 0

  QtObject {
    id: fakeBar
    property string position: "top"
    property int barSize: 28
    property string fontFamily: "synthetic-monospace"
    property color barForeground: "#d8d0d5"
    property var activePopout: null
    function requestPopout(owner) { activePopout = owner }
    function releasePopout(owner) { if (activePopout === owner) activePopout = null }
  }

  PanelWindow {
    id: fakeBarWindow
    visible: true
    color: "transparent"
    implicitWidth: 640
    implicitHeight: 28
    anchors { top: true; left: true; right: true }

    Item { id: anchor; x: 300; y: 2; width: 28; height: 24 }

    QtObject {
      id: syntheticController
      property var messages: [
        { id: "incoming", role: "assistant", text: "Synthetic incoming." },
        { id: "outgoing", role: "user", text: "<plain outgoing>" }
      ]
      property string connectionState: "connected"
      property string statusText: "Synthetic controller only."
      property string modelLabel: "Preview model"
      property bool streaming: false
      property bool canSend: true
      property bool canStop: false
      property string sent: ""
      function send(text) { sent = text }
      function abort() { sent = "aborted" }
    }

    Plugin.Panel {
      id: popup
      anchorItem: anchor
      bar: fakeBar
      chatController: null
      onRequestNativeOpen: shell.nativeOpenCount++
    }
  }

  function hex(color) { return color.toString().toLowerCase() }

  function check(condition, message) {
    if (!condition) {
      failures++
      console.error("T11_FAIL " + message)
    }
  }

  Timer {
    interval: 600
    running: true
    repeat: false
    onTriggered: {
      popup.open()
      check(popup.opened === true, "popup does not expose the SDK panel lifecycle")
      check(popup.panelOpen === true, "popup is not an independent SDK surface")
      check(popup.themeFontFamily === "synthetic-monospace", "popup did not use the SDK bar font")
      check(popup.canSend === null || popup.canSend === false, "disconnected popup can send")
      popup.chatController = syntheticController
      check(popup.messageCount === 2 && popup.messages[0].role === "assistant" && popup.messages[1].role === "user", "connected roles are not rendered")
      check(popup.messages[1].text === "<plain outgoing>", "plain text message changed")
      popup.focusComposer()
      console.log("T11_COLORS foreground=" + hex(popup.composerForeground) + " placeholder=" + hex(popup.composerPlaceholder) + " selection=" + hex(popup.composerSelection) + " background=" + hex(popup.composerBackground) + " border=" + hex(popup.composerBorder) + " focused=" + popup.composerFocused)
      check(popup.composerFocused, "composer did not receive focus")
      check(hex(popup.composerForeground).endsWith("e1d1dc"), "composer foreground ignored popup text theme")
      check(hex(popup.composerPlaceholder).endsWith("837481"), "composer placeholder ignored muted theme")
      check(hex(popup.composerSelection) !== hex(popup.composerForeground), "composer selection ignored SDK selection theme")
      check(hex(popup.composerBackground) !== hex(popup.composerForeground), "composer background ignored SDK control theme")
      check(hex(popup.composerBorder).endsWith("e1d1dc"), "focused composer border ignored SDK focus theme")
      popup.sendMessage("synthetic send")
      check(syntheticController.sent === "synthetic send", "connected send did not reach synthetic controller")
      popup.requestNativeOpen()
      check(shell.nativeOpenCount === 1, "native open signal did not reach fake handler")
      console.log("T11_RESULT failures=" + shell.failures)
      Qt.exit(shell.failures === 0 ? 0 : 1)
    }
  }
}
