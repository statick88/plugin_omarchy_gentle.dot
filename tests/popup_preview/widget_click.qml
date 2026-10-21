import QtQuick
import Quickshell
import "plugin" as Plugin

// Drives the production BarWidget.qml with synthetic input only: the fake
// launcher records that the official native launcher was reached, and no real
// Gentle Dot process is ever started.
ShellRoot {
  id: shell

  property int failures: 0

  QtObject {
    id: fakeBar
    property string position: "top"
    property int barSize: 28
    property string fontFamily: "synthetic-monospace"
    property color barForeground: "#d8d0d5"
    property color urgent: "#ff8fa3"
    property bool foregroundAnimationEnabled: false
    property var activePopout: null
    function requestPopout(owner) { activePopout = owner }
    function releasePopout(owner) { if (activePopout === owner) activePopout = null }
    function hideTooltip(item) {}
    function showTooltip(item, text) {}
    function registerClickTarget(item) {}
    function unregisterClickTarget(item) {}
  }

  PanelWindow {
    id: fakeBarWindow
    visible: true
    color: "transparent"
    implicitWidth: 640
    implicitHeight: 28
    anchors { top: true; left: true; right: true }

    Item { id: anchor; x: 300; y: 2; width: 28; height: 24 }

    Plugin.BarWidget {
      id: widget
      anchors.fill: anchor
      bar: fakeBar
      settings: ({ "appPath": Quickshell.env("GENTLE_FAKE_LAUNCHER") })
    }
  }

  function check(condition, message) {
    if (!condition) {
      failures++
      console.error("T22_FAIL " + message)
    }
  }

  Component.onCompleted: {
    // The published contract: a left click reaches the official native panel.
    widget.handlePress(Qt.LeftButton)
  }

  Timer {
    interval: 1200
    running: true
    repeat: false
    onTriggered: {
      check(widget.launchError === "", "left click reported a launch failure: " + widget.launchError)
      check(widget.opened === false, "left click opened the chat popup")
      // The owned popup stays reachable through the secondary gesture.
      widget.handlePress(Qt.RightButton)
      check(widget.opened === true, "right click did not open the chat popup")
      widget.handlePress(Qt.RightButton)
      check(widget.opened === false, "right click did not close the chat popup")
      console.log("T22_RESULT failures=" + shell.failures)
      Qt.exit(shell.failures === 0 ? 0 : 1)
    }
  }
}
