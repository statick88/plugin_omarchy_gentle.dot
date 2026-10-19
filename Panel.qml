pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
import QtQuick.Dialogs
import qs.Commons
import qs.Commons as Commons
import qs.Ui as Ui

// Owned presentation shell. T12 may supply chatController; it never creates one.
Ui.Panel {
    id: root

    property Item anchorItem: null
    property var chatController: null
    signal requestNativeOpen()

    readonly property var messages: chatController && Array.isArray(chatController.messages)
        ? chatController.messages : []
    readonly property string connectionState: chatController && chatController.connectionState
        ? chatController.connectionState : "disconnected"
    readonly property string statusText: chatController && chatController.statusText
        ? chatController.statusText : "Chat is unavailable here. Open Gentle Dot to use the installed app."
    readonly property string modelLabel: chatController && chatController.modelLabel
        ? chatController.modelLabel : "Gentle Dot"
    readonly property bool streaming: chatController && chatController.streaming === true
    readonly property bool canSend: chatController && typeof chatController.send === "function"
        && chatController.canSend === true
    readonly property bool canStop: chatController && typeof chatController.abort === "function"
        && chatController.canStop === true
    readonly property bool panelOpen: opened
    readonly property int messageCount: messages.length
    readonly property string themeFontFamily: bar ? bar.fontFamily : Style.font.family
    readonly property color themeSurface: Commons.Color.popups.background
    // Exposed for the isolated rendered harness; values bind to the live input.
    readonly property color composerForeground: composer.color
    readonly property color composerPlaceholder: composer.placeholderTextColor
    readonly property color composerSelection: composer.selectionColor
    readonly property color composerBackground: composerBackground.color
    readonly property color composerBorder: composerBackground.border.color

    function sendMessage(text) {
        var plain = String(text || "").trim()
        if (canSend && !streaming && plain.length > 0) chatController.send(plain)
    }
    function stopMessage() { if (canStop) chatController.abort() }
    function focusComposer() { composer.forceActiveFocus() }
    readonly property bool composerFocused: composer.activeFocus

    Ui.KeyboardPanel {
        id: panel
        anchorItem: root.anchorItem
        owner: root
        bar: root.bar
        open: root.opened
        focusTarget: keyCatcher
        contentWidth: panel.fittedContentWidth(Style.space(394), Style.space(420))
        contentHeight: panel.cappedContentHeight(Style.space(407))

        Ui.PanelKeyCatcher {
            id: keyCatcher
            anchors.fill: parent
            blocked: composer.activeFocus
            onCloseRequested: root.close()

            Item {
                anchors.fill: parent

                Item {
                    id: header
                    width: parent.width
                    height: Style.space(38)
                    Text {
                        id: back
                        anchors.left: parent.left
                        anchors.verticalCenter: parent.verticalCenter
                        text: "‹"
                        color: Commons.Color.popups.text
                        font.family: root.themeFontFamily
                        font.pixelSize: Style.font.heading
                        MouseArea { anchors.fill: parent; onClicked: root.close() }
                    }
                    Column {
                        anchors.left: back.right; anchors.leftMargin: Style.spacing.md
                        anchors.verticalCenter: parent.verticalCenter
                        Text { text: root.modelLabel; color: Commons.Color.popups.text; font.family: root.themeFontFamily; font.pixelSize: Style.font.body; font.bold: true }
                        Text { text: root.connectionState; color: Commons.Color.muted; font.family: root.themeFontFamily; font.pixelSize: Style.font.caption }
                    }
                    Text {
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        text: "↗"; color: Commons.Color.popups.text; font.family: root.themeFontFamily; font.pixelSize: Style.font.title
                        MouseArea { anchors.fill: parent; onClicked: root.requestNativeOpen() }
                    }
                }

                Ui.PanelSeparator { id: rule; anchors.top: header.bottom; width: parent.width; foreground: Commons.Color.popups.text }

                PairingForm {
                    id: pairing
                    anchors.top: rule.bottom
                    width: parent.width
                    controller: root.chatController
                    visible: root.connectionState !== "connected"
                }

                Ui.Toggle {
                    id: writeConsent
                    anchors.top: pairing.visible ? pairing.bottom : rule.bottom
                    width: parent.width; visible: root.connectionState === "connected" && root.chatController && typeof root.chatController.setWrite === "function"
                    label: "Enable shared writing"
                    description: "Sending while busy can redirect the current response. Stop affects all clients."
                    checked: root.chatController && root.chatController.writeWanted === true
                    foreground: Commons.Color.popups.text; accent: Commons.Color.accent
                    onClicked: root.chatController.setWrite(!checked)
                }

                ListView {
                    id: transcript
                    anchors.top: writeConsent.visible ? writeConsent.bottom : (pairing.visible ? pairing.bottom : rule.bottom); anchors.bottom: status.top
                    width: parent.width; clip: true; model: root.messages
                    spacing: Style.spacing.md; topMargin: Style.spacing.md; bottomMargin: Style.spacing.md
                    delegate: Item {
                        required property var modelData
                        width: transcript.width
                        height: bubble.implicitHeight
                        Rectangle {
                            id: bubble
                            anchors.left: modelData.role === "user" ? undefined : parent.left
                            anchors.right: modelData.role === "user" ? parent.right : undefined
                            width: Math.min(parent.width * .82, body.implicitWidth + Style.spacing.xxl * 2)
                            implicitHeight: body.implicitHeight + Style.spacing.md * 2
                            radius: Style.cornerRadius
                            color: modelData.role === "user" ? Style.selectedFillFor(Commons.Color.popups.text, Commons.Color.accent) : Style.normalFillFor(Commons.Color.popups.text, Commons.Color.accent)
                            Text { id: body; anchors.fill: parent; anchors.margins: Style.spacing.md; text: String(modelData.text || ""); textFormat: Text.PlainText; wrapMode: Text.Wrap; color: Commons.Color.popups.text; font.family: root.themeFontFamily; font.pixelSize: Style.font.body }
                        }
                    }
                }

                Text {
                    id: status
                    anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: composerRow.top
                    text: root.chatController && root.chatController.pendingStop ? "Stop affects every client. Confirm?" : root.statusText; textFormat: Text.PlainText; wrapMode: Text.Wrap
                    color: Commons.Color.muted; font.family: root.themeFontFamily; font.pixelSize: Style.font.caption
                }
                Item {
                    id: composerRow
                    anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                    height: Style.space(38)
                    TextArea {
                        id: composer
                        anchors.left: parent.left; anchors.right: send.left; anchors.top: parent.top; anchors.bottom: parent.bottom
                        enabled: root.canSend && !root.streaming
                        placeholderText: root.canSend ? "Message Gentle Dot" : "Open Gentle Dot to chat"
                        color: Commons.Color.popups.text
                        placeholderTextColor: Commons.Color.muted
                        selectionColor: Style.selectionFillFor(Commons.Color.popups.text, Commons.Color.accent)
                        selectedTextColor: Commons.Color.popups.text
                        font.family: root.themeFontFamily; font.pixelSize: Style.font.body
                        background: Rectangle {
                            id: composerBackground
                            color: Style.controlFill(composer.activeFocus, composer.hovered, Commons.Color.popups.text, Commons.Color.accent)
                            border.width: Style.controlBorderWidth(composer.activeFocus, composer.hovered)
                            border.color: Style.controlBorder(composer.activeFocus, composer.hovered, Commons.Color.popups.text, Commons.Color.accent)
                            radius: Style.cornerRadius
                        }
                        Keys.onReturnPressed: function(event) { if (root.sendMessage(text) !== false) text = ""; event.accepted = true }
                    }
                    Text {
                        id: send
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        text: root.streaming ? "■" : "➤"; color: Commons.Color.accent; font.family: root.themeFontFamily; font.pixelSize: Style.font.title
                        enabled: root.streaming ? root.canStop : root.canSend && composer.text.trim().length > 0
                        opacity: enabled ? 1 : .4
                        MouseArea { anchors.fill: parent; enabled: send.enabled; onClicked: { if (root.streaming) root.chatController.requestStop(); else if (root.sendMessage(composer.text) !== false) composer.text = "" } }
                    }
                    Row {
                        anchors.right: parent.right; anchors.bottom: parent.top; visible: root.chatController && root.chatController.pendingStop
                        Ui.Button { text: "Confirm Stop"; foreground: Commons.Color.popups.text; accent: Commons.Color.accent; bordered: true; onClicked: root.chatController.abort(true) }
                        Ui.Button { text: "Cancel"; foreground: Commons.Color.popups.text; accent: Commons.Color.accent; bordered: true; onClicked: root.chatController.cancelStop() }
                    }
                }
            }
        }
    }

    component PairingForm: Item {
        id: pairingRoot
        property var controller: null
        property bool accepted: false
        implicitHeight: column.implicitHeight + Style.spacing.md

        function connect() { if (controller) controller.connect(endpointInput.text, tokenInput.text, accepted) }
        function disconnect() {
            if (controller) controller.disconnect()
            accepted = false
            tokenInput.text = ""
            endpointInput.text = "ws://127.0.0.1:4317/ws"
        }

        Column {
            id: column
            width: parent.width
            spacing: Style.spacing.sm
            Text { width: parent.width; textFormat: Text.PlainText; wrapMode: Text.Wrap; text: "Pair this popup with a local Gentle Dot session. It can read shared-session history only; sending arrives later."; color: Commons.Color.muted; font.family: root.themeFontFamily; font.pixelSize: Style.font.caption }
            Ui.TextField {
                id: endpointInput
                width: parent.width
                text: "ws://127.0.0.1:4317/ws"
                placeholderText: "Loopback endpoint"
                foreground: Commons.Color.popups.text
                accent: Commons.Color.accent
            }
            Row {
                width: parent.width; spacing: Style.spacing.sm
                Ui.TextField {
                    id: tokenInput
                    width: parent.width - pick.implicitWidth - parent.spacing
                    placeholderText: "Absolute path to the selected token file"
                    foreground: Commons.Color.popups.text
                    accent: Commons.Color.accent
                }
                Ui.Button { id: pick; text: "Choose file"; foreground: Commons.Color.popups.text; accent: Commons.Color.accent; bordered: true; onClicked: picker.open() }
            }
            Ui.Toggle {
                width: parent.width
                label: "I consent to read-only history"
                description: "The selected local capability file stays in memory; this shares the existing Gentle Dot session."
                checked: pairingRoot.accepted
                foreground: Commons.Color.popups.text
                accent: Commons.Color.accent
                onClicked: pairingRoot.accepted = !pairingRoot.accepted
            }
            Row {
                spacing: Style.spacing.sm
                Ui.Button { text: "Connect"; foreground: Commons.Color.popups.text; accent: Commons.Color.accent; bordered: true; opacity: pairingRoot.accepted && tokenInput.text.length > 0 ? 1 : .45; onClicked: pairingRoot.connect() }
                Ui.Button { text: "Disconnect"; foreground: Commons.Color.popups.text; accent: Commons.Color.accent; bordered: true; onClicked: pairingRoot.disconnect() }
            }
        }
        FileDialog {
            id: picker
            title: "Choose Gentle Dot token file"
            fileMode: FileDialog.OpenFile
            onAccepted: tokenInput.text = decodeURIComponent(selectedFile.toString().replace(/^file:\/\//, ""))
        }
    }
}
