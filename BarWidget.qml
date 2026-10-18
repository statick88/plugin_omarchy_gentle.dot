pragma ComponentBehavior: Bound

import QtQuick
import Qt5Compat.GraphicalEffects
import Quickshell.Io
import qs.Ui as Ui

Ui.BarWidget {
    id: root
    moduleName: "statick.gentle-dot"

    property string launchError: ""
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight

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
        tooltipText: root.launchError || "Gentle Dot for Omarchy — toggle chat and settings"
        onPressed: function(button) {
            if (button === Qt.LeftButton && !toggleProcess.running) {
                root.launchError = ""
                toggleProcess.running = true
            }
        }
    }
}
