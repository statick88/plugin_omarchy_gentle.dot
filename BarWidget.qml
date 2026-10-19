pragma ComponentBehavior: Bound

import QtQuick
import Qt5Compat.GraphicalEffects
import Quickshell.Io
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "statick.gentle-dot"

    property string launchError: ""
    // T12 supplies this narrow controller; absent means disconnected and fail-closed.
    property var chatController: null
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

    function openNativeApp() {
        if (!toggleProcess.running) {
            launchError = ""
            toggleProcess.running = true
        }
    }

    Panel {
        id: popup
        parent: root
        x: Math.min(Math.max(0, button.x + button.width - width), Math.max(0, root.width - width))
        y: button.y + button.height + 8
        anchorItem: button
        chatController: root.chatController
        onRequestNativeOpen: {
            popup.close()
            root.openNativeApp()
        }
    }

    Process {
        id: toggleProcess
        // Resolve next to the QML file, including paths with spaces.
        command: ["sh", decodeURIComponent(Qt.resolvedUrl("toggle.sh").toString().replace(/^file:\/\//, "")), root.setting("appPath", "")]
        stderr: StdioCollector { id: launchStderr }
        onExited: function(exitCode) {
            if (exitCode !== 0)
                root.launchError = launchStderr.text.trim()
                    || "Gentle Dot could not start (exit " + exitCode + ")."
        }
    }

    Ui.BarIconButton {
        id: button
        anchors.fill: parent
        bar: root.bar
        iconComponent: Component {
            Item {
                Image {
                    id: rose
                    anchors.fill: parent
                    source: Qt.resolvedUrl("assets/rose-glyph.svg")
                    fillMode: Image.PreserveAspectFit
                    sourceSize.width: Math.round(width * Screen.devicePixelRatio)
                    sourceSize.height: Math.round(height * Screen.devicePixelRatio)
                    visible: false
                }
                ColorOverlay {
                    anchors.fill: rose
                    source: rose
                    color: button.active && button.useActiveColor
                        ? button.activeColor : button.foreground
                }
            }
        }
        tooltipText: root.launchError || "Gentle Dot — open chat popup"
        onPressed: function(mouseButton) {
            if (mouseButton === Qt.LeftButton)
                popup.opened ? popup.close() : popup.open()
        }
    }
}
