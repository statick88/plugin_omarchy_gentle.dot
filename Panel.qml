pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls
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

                ListView {
                    id: transcript
                    anchors.top: rule.bottom; anchors.bottom: status.top
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
                    text: root.statusText; textFormat: Text.PlainText; wrapMode: Text.Wrap
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
                        Keys.onReturnPressed: function(event) { root.sendMessage(text); event.accepted = true }
                    }
                    Text {
                        id: send
                        anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        text: root.streaming ? "■" : "➤"; color: Commons.Color.accent; font.family: root.themeFontFamily; font.pixelSize: Style.font.title
                        enabled: root.streaming ? root.canStop : root.canSend && composer.text.trim().length > 0
                        opacity: enabled ? 1 : .4
                        MouseArea { anchors.fill: parent; enabled: send.enabled; onClicked: root.streaming ? root.stopMessage() : root.sendMessage(composer.text) }
                    }
                }
            }
        }
    }
}
