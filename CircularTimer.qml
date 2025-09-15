import QtQuick 2.15
import QtQuick.Controls 2.15

Item {
    id: root
    
    // Enable keyboard focus
    focus: true
    
    // add this font to the project from font file
    FontLoader {
            id: customFontLoader
            source: "Assets/Fonts/good_times_rg.ttf" // Adjust path if not using resources
        }
    
    // Public properties for customization
    property int timerSeconds: 60
    property real progressValue: 0.0
    property bool isRunning: false
    property QtObject backend
    
    // Internal properties
    property int previousSeconds: 60
    property real scaleFactor: Math.min(width / 400, height / 400)
    property real timerSize: Math.min(width * 0.8, height * 0.8, 500)
    
    // // Color theme - your specified palette
    // readonly property color oxfordBlue: "#0C1936"
    // readonly property color uclaBlue: "#4574AD"
    // readonly property color oxfordBlue2: "#1B2437"
    // readonly property color oxfordBlue3: "#0D1D3C"
    // readonly property color yinmnBlue: "#48536D"

    // theme colors 1
    readonly property color oxfordBlue: "#0C1936" // Darkest blue
    readonly property color uclaBlue: "#4574AD" // Main blue
    readonly property color oxfordBlue2: "#1B2437" // Medium blue
    readonly property color oxfordBlue3: "#0D1D3C" // Light blue
    readonly property color yinmnBlue: "#48536D" // Lightest blue

    // ========== GRADIENT COLORS FOR EASY MODIFICATION ==========
    // Critical state (≤5 seconds) - Red gradient
    readonly property color criticalRed1: "#ff3333"
    readonly property color criticalRed2: "#ff6b6b"
    readonly property color criticalRed3: "#e74c3c"
    
    // Warning state (≤10 seconds) - Orange/Pink gradient
    readonly property color warningOrange1: "#ff6b6b"
    readonly property color warningOrange2: "#ff8e53"
    readonly property color warningOrange3: "#ff6b9d"
    
    // Transition state (≤30 seconds) - Orange/Blue gradient
    readonly property color transitionOrange: "#f39c12"
    
    // Normal state (>30 seconds) - Blue gradient (uses existing theme colors)
    // uclaBlue, yinmnBlue, oxfordBlue2

   
    

    
    
    // Connections to backend signals
    Connections {
        target: backend

        function onTimerValueChanged(seconds, progress) {
            if (isRunning && seconds !== previousSeconds && seconds >= 0) {
                // Trigger animations
                numberAnimation.start();
                rippleEffect.start();
                
                // Warning effects for last 10 seconds
                if (seconds <= 10 && seconds > 0) {
                    warningPulse.start();
                }
                
                // Game over effect
                if (seconds === 0) {
                    gameOverEffect.start();
                }
            }
            
            previousSeconds = timerSeconds;
            timerSeconds = seconds;
            progressValue = progress;
        }

        function onCountdownStarted() {
            isRunning = true;
            startAnimation.start();
        }

        function onCountdownStopped() {
            isRunning = false;
            stopAnimation.start();
        }
    }

    // Auto-start timer when component is ready
    Component.onCompleted: {
        if (backend) {
            // Auto-start the timer
            backend.start_countdown();
        }
    }

    // Keyboard input handling
    Keys.onPressed: {
        if (event.key === Qt.Key_S) {
            if (backend) {
                if (isRunning) {
                    backend.stop_countdown();
                } else {
                    backend.start_countdown();
                }
            }
            event.accepted = true;
        }
    }

    // Main circular timer container
    Rectangle {
        id: timerContainer
        width: timerSize
        height: timerSize
        anchors.centerIn: parent
        color: "transparent"
        
        // Transform for animations
        transform: [
            Scale {
                id: containerScale
                origin.x: timerContainer.width / 2
                origin.y: timerContainer.height / 2
                xScale: 1.0
                yScale: 1.0
            },
            Translate {
                id: containerShake
                x: 0
                y: 0
            }
        ]
        
        // Background ring
        Rectangle {
            anchors.fill: parent
            radius: width / 2
            color: "transparent"
            border.color: timerSeconds <= 10 ? warningOrange1 : uclaBlue
            border.width: Math.max(6, 8 * scaleFactor)
            opacity: 0.3
            
            Behavior on border.color { ColorAnimation { duration: 300 } }
        }

        // Ripple effects
        Rectangle {
            id: ripple1
            anchors.centerIn: parent
            width: 0; height: 0
            radius: width / 2
            color: "transparent"
            border.width: Math.max(2, 3 * scaleFactor)
            opacity: 0
            
            border.color: timerSeconds <= 10 ? warningOrange1 : uclaBlue
        }
        
        Rectangle {
            id: ripple2
            anchors.centerIn: parent
            width: 0; height: 0
            radius: width / 2
            color: "transparent"
            border.width: Math.max(2, 3 * scaleFactor)
            opacity: 0
            
            border.color: timerSeconds <= 10 ? warningOrange2 : yinmnBlue
        }
        
        Rectangle {
            id: ripple3
            anchors.centerIn: parent
            width: 0; height: 0
            radius: width / 2
            color: "transparent"
            border.width: Math.max(2, 3 * scaleFactor)
            opacity: 0
            
            border.color: timerSeconds <= 10 ? warningOrange3 : oxfordBlue2
        }

        // Enhanced progress circle
        Canvas {
            id: progressCanvas
            anchors.fill: parent
            
            property real glowIntensity: isRunning ? (timerSeconds <= 10 ? 1.0 : 0.6) : 0.3
            property real pulseScale: 1.0
            
            transform: [
                Rotation {
                    id: canvasRotation
                    origin.x: progressCanvas.width / 2
                    origin.y: progressCanvas.height / 2
                    angle: 0
                },
                Scale {
                    id: canvasPulse
                    origin.x: progressCanvas.width / 2
                    origin.y: progressCanvas.height / 2
                    xScale: progressCanvas.pulseScale
                    yScale: progressCanvas.pulseScale
                }
            ]
            
            // Continuous pulse when running
            SequentialAnimation on pulseScale {
                loops: Animation.Infinite
                running: isRunning
                NumberAnimation { 
                    from: 1.0; to: 1.03; 
                    duration: 1500; 
                    easing.type: Easing.InOutSine 
                }
                NumberAnimation { 
                    from: 1.03; to: 1.0; 
                    duration: 1500; 
                    easing.type: Easing.InOutSine 
                }
            }
            
            Behavior on glowIntensity {
                NumberAnimation { duration: 500; easing.type: Easing.InOutQuad }
            }
            
            onPaint: {
                var ctx = getContext("2d");
                ctx.clearRect(0, 0, width, height);
                
                var centerX = width / 2;
                var centerY = height / 2;
                var radius = (width - (24 * scaleFactor)) / 2;
                var startAngle = -Math.PI / 2;
                var progressAngle = (progressValue / 100) * 2 * Math.PI;
                
                // Background track
                ctx.beginPath();
                ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
                ctx.lineWidth = Math.max(12, 18 * scaleFactor);
                ctx.strokeStyle = Qt.rgba(0.1, 0.1, 0.2, 0.3);
                ctx.stroke();
                
                // Outer glow
                if (glowIntensity > 0) {
                    ctx.beginPath();
                    ctx.arc(centerX, centerY, radius + (6 * scaleFactor), startAngle, startAngle + progressAngle);
                    ctx.lineWidth = Math.max(8, 12 * scaleFactor);
                    if (timerSeconds <= 10) {
                        ctx.strokeStyle = Qt.rgba(1, 0.4, 0.4, glowIntensity * 0.5);
                    } else {
                        ctx.strokeStyle = Qt.rgba(0.27, 0.45, 0.68, glowIntensity * 0.4);
                    }
                    ctx.stroke();
                }
                
                // Create gradient
                var gradient = ctx.createLinearGradient(
                    centerX - radius, centerY - radius, 
                    centerX + radius, centerY + radius
                );
                
                if (timerSeconds <= 5) {
                    gradient.addColorStop(0, criticalRed1);
                    gradient.addColorStop(0.5, warningOrange1);
                    gradient.addColorStop(1, warningOrange3);
                } else if (timerSeconds <= 10) {
                    gradient.addColorStop(0, warningOrange1);
                    gradient.addColorStop(0.5, warningOrange2);
                    gradient.addColorStop(1, "#ff6b9d");
                } else if (timerSeconds <= 30) {
                    gradient.addColorStop(0, transitionOrange);
                    gradient.addColorStop(0.5, uclaBlue);
                    gradient.addColorStop(1, yinmnBlue);
                } else {
                    gradient.addColorStop(0, uclaBlue);
                    gradient.addColorStop(0.5, yinmnBlue);
                    gradient.addColorStop(1, oxfordBlue2);
                }
                
                // Main progress arc
                ctx.beginPath();
                ctx.arc(centerX, centerY, radius, startAngle, startAngle + progressAngle);
                ctx.lineWidth = Math.max(16, 24 * scaleFactor);
                ctx.strokeStyle = gradient;
                ctx.lineCap = "round";
                ctx.stroke();
                
                // Inner highlight
                ctx.beginPath();
                ctx.arc(centerX, centerY, radius, startAngle, startAngle + progressAngle);
                ctx.lineWidth = Math.max(6, 10 * scaleFactor);
                var shineAlpha = timerSeconds <= 10 ? 0.8 : 0.5;
                ctx.strokeStyle = Qt.rgba(1, 1, 1, shineAlpha * glowIntensity);
                ctx.lineCap = "round";
                ctx.stroke();
                
                // Progress indicator dot
                if (progressAngle > 0.1) {
                    var dotX = centerX + radius * Math.cos(startAngle + progressAngle);
                    var dotY = centerY + radius * Math.sin(startAngle + progressAngle);
                    
                    // Outer dot glow
                    ctx.beginPath();
                    ctx.arc(dotX, dotY, Math.max(6, 10 * scaleFactor), 0, 2 * Math.PI);
                    ctx.fillStyle = Qt.rgba(1, 1, 1, 0.6 * glowIntensity);
                    ctx.fill();
                    
                    // Inner dot
                    ctx.beginPath();
                    ctx.arc(dotX, dotY, Math.max(3, 5 * scaleFactor), 0, 2 * Math.PI);
                    if (timerSeconds <= 10) {
                        ctx.fillStyle = warningOrange1;
                    } else {
                        ctx.fillStyle = uclaBlue;
                    }
                    ctx.fill();
                }
            }
        }

        // Timer text display
        Text {
            id: timerText
            text: formatTime(timerSeconds)
            font.family: customFontLoader.name
            font.pixelSize: Math.max(24, 48 * scaleFactor)
            font.bold: true
            color: timerSeconds <= 10 ? uclaBlue : yinmnBlue
            anchors.centerIn: parent
            
            renderType: Text.NativeRendering
            antialiasing: true
            
            transform: [
                Scale {
                    id: textScale
                    origin.x: timerText.width / 2
                    origin.y: timerText.height / 2
                    xScale: 1.0
                    yScale: 1.0
                },
                Rotation {
                    id: textRotation
                    origin.x: timerText.width / 2
                    origin.y: timerText.height / 2
                    angle: 0
                }
            ]
            
            Behavior on color { ColorAnimation { duration: 300 } }
        }

        // Status text
        Text {
            id: statusText
            text: isRunning ? "RUNNING - Press 'S' to Stop" : "READY - Press 'S' to Start"
            font.family: customFontLoader.name
            font.pixelSize: Math.max(8, 12 * scaleFactor)
            font.bold: true
            color: isRunning ? uclaBlue : yinmnBlue
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: timerText.bottom
            anchors.topMargin: 10 * scaleFactor
            
            renderType: Text.NativeRendering
            antialiasing: true
            
            SequentialAnimation on opacity {
                loops: Animation.Infinite
                running: isRunning
                NumberAnimation { from: 0.7; to: 1.0; duration: 800 }
                NumberAnimation { from: 1.0; to: 0.7; duration: 800 }
            }
        }
    }

    // ============= ANIMATIONS =============
    
    // Number animation when timer updates
    ParallelAnimation {
        id: numberAnimation
        
        SequentialAnimation {
            NumberAnimation {
                target: textScale
                properties: "xScale,yScale"
                from: 1.0
                to: timerSeconds <= 10 ? 1.3 : 1.2
                duration: timerSeconds <= 10 ? 100 : 150
                easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: textScale
                properties: "xScale,yScale"
                to: 1.0
                duration: timerSeconds <= 10 ? 200 : 250
                easing.type: Easing.OutElastic
            }
        }
        
        SequentialAnimation {
            ColorAnimation {
                target: timerText
                property: "color"
                from: "white"
                to: {
                    if (timerSeconds <= 5) return criticalRed1;
                    else if (timerSeconds <= 10) return warningOrange1;
                    else if (timerSeconds <= 30) return "#f39c12";
                    else return uclaBlue;
                }
                duration: 80
            }
            ColorAnimation {
                target: timerText
                property: "color"
                to: "white"
                duration: 150
            }
        }
        
        SequentialAnimation {
            NumberAnimation {
                target: textRotation
                property: "angle"
                from: 0
                to: timerSeconds <= 10 ? (Math.random() > 0.5 ? 6 : -6) : 3
                duration: 100
            }
            NumberAnimation {
                target: textRotation
                property: "angle"
                to: 0
                duration: 200
                easing.type: Easing.OutElastic
            }
        }
    }
    
    // Ripple effect animation
    ParallelAnimation {
        id: rippleEffect
        
        // First ripple
        SequentialAnimation {
            PauseAnimation { duration: timerSeconds <= 10 ? 0 : 0 }
            ParallelAnimation {
                NumberAnimation {
                    target: ripple1
                    properties: "width,height"
                    from: 0
                    to: timerSize * (1.0 + (timerSeconds <= 10 ? 0.2 : 0))
                    duration: timerSeconds <= 10 ? 600 : 800
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: ripple1
                    property: "opacity"
                    from: timerSeconds <= 10 ? 0.9 : 0.7
                    to: 0
                    duration: timerSeconds <= 10 ? 600 : 800
                    easing.type: Easing.OutQuad
                }
            }
            PropertyAction { 
                target: ripple1
                properties: "width,height,opacity"
                value: 0
            }
        }
        
        // Second ripple
        SequentialAnimation {
            PauseAnimation { duration: timerSeconds <= 10 ? 80 : 120 }
            ParallelAnimation {
                NumberAnimation {
                    target: ripple2
                    properties: "width,height"
                    from: 0
                    to: timerSize * (1.15 + (timerSeconds <= 10 ? 0.2 : 0))
                    duration: timerSeconds <= 10 ? 600 : 800
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: ripple2
                    property: "opacity"
                    from: timerSeconds <= 10 ? 0.9 : 0.7
                    to: 0
                    duration: timerSeconds <= 10 ? 600 : 800
                    easing.type: Easing.OutQuad
                }
            }
            PropertyAction { 
                target: ripple2
                properties: "width,height,opacity"
                value: 0
            }
        }
        
        // Third ripple
        SequentialAnimation {
            PauseAnimation { duration: timerSeconds <= 10 ? 160 : 240 }
            ParallelAnimation {
                NumberAnimation {
                    target: ripple3
                    properties: "width,height"
                    from: 0
                    to: timerSize * (1.3 + (timerSeconds <= 10 ? 0.2 : 0))
                    duration: timerSeconds <= 10 ? 600 : 800
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: ripple3
                    property: "opacity"
                    from: timerSeconds <= 10 ? 0.9 : 0.7
                    to: 0
                    duration: timerSeconds <= 10 ? 600 : 800
                    easing.type: Easing.OutQuad
                }
            }
            PropertyAction { 
                target: ripple3
                properties: "width,height,opacity"
                value: 0
            }
        }
    }
    
    // Warning pulse for danger zone
    SequentialAnimation {
        id: warningPulse
        loops: 2
        ParallelAnimation {
            NumberAnimation {
                target: containerScale
                properties: "xScale,yScale"
                from: 1.0; to: 1.04
                duration: 120
            }
            NumberAnimation {
                target: timerContainer
                property: "opacity"
                from: 1.0; to: 0.8
                duration: 120
            }
        }
        ParallelAnimation {
            NumberAnimation {
                target: containerScale
                properties: "xScale,yScale"
                from: 1.04; to: 1.0
                duration: 120
            }
            NumberAnimation {
                target: timerContainer
                property: "opacity"
                from: 0.8; to: 1.0
                duration: 120
            }
        }
    }
    
    // Game over explosion effect
    ParallelAnimation {
        id: gameOverEffect
        
        SequentialAnimation {
            NumberAnimation {
                target: containerScale
                properties: "xScale,yScale"
                from: 1.0; to: 1.8
                duration: 300
                easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: containerScale
                properties: "xScale,yScale"
                from: 1.8; to: 1.0
                duration: 600
                easing.type: Easing.OutBounce
            }
        }
        
        SequentialAnimation {
            NumberAnimation {
                target: canvasRotation
                property: "angle"
                from: 0; to: 720
                duration: 900
                easing.type: Easing.OutQuad
            }
            PropertyAction { target: canvasRotation; property: "angle"; value: 0 }
        }
        
        // Explosive ripples
        SequentialAnimation {
            PauseAnimation { duration: 100 }
            ParallelAnimation {
                // First explosive ripple
                SequentialAnimation {
                    PauseAnimation { duration: 0 }
                    ParallelAnimation {
                        NumberAnimation {
                            target: ripple1
                            properties: "width,height"
                            from: 0
                            to: timerSize * 2.0
                            duration: 1000
                            easing.type: Easing.OutQuad
                        }
                        NumberAnimation {
                            target: ripple1
                            property: "opacity"
                            from: 1.0
                            to: 0
                            duration: 1000
                            easing.type: Easing.OutQuad
                        }
                    }
                }
                
                // Second explosive ripple
                SequentialAnimation {
                    PauseAnimation { duration: 150 }
                    ParallelAnimation {
                        NumberAnimation {
                            target: ripple2
                            properties: "width,height"
                            from: 0
                            to: timerSize * 2.5
                            duration: 1200
                            easing.type: Easing.OutQuad
                        }
                        NumberAnimation {
                            target: ripple2
                            property: "opacity"
                            from: 1.0
                            to: 0
                            duration: 1200
                            easing.type: Easing.OutQuad
                        }
                    }
                }
                
                // Third explosive ripple
                SequentialAnimation {
                    PauseAnimation { duration: 300 }
                    ParallelAnimation {
                        NumberAnimation {
                            target: ripple3
                            properties: "width,height"
                            from: 0
                            to: timerSize * 3.0
                            duration: 1400
                            easing.type: Easing.OutQuad
                        }
                        NumberAnimation {
                            target: ripple3
                            property: "opacity"
                            from: 1.0
                            to: 0
                            duration: 1400
                            easing.type: Easing.OutQuad
                        }
                    }
                }
            }
        }
    }
    
    // Start animation
    ParallelAnimation {
        id: startAnimation
        NumberAnimation {
            target: timerContainer
            property: "opacity"
            from: 0.3; to: 1.0
            duration: 500
            easing.type: Easing.OutQuad
        }
        NumberAnimation {
            target: containerScale
            properties: "xScale,yScale"
            from: 0.8; to: 1.0
            duration: 500
            easing.type: Easing.OutBack
        }
    }
    
    // Stop animation
    NumberAnimation {
        id: stopAnimation
        target: timerContainer
        property: "opacity"
        from: 1.0; to: 0.7
        duration: 300
        easing.type: Easing.InQuad
    }

    // Helper function to format time
    function formatTime(seconds) {
        var mins = Math.floor(seconds / 60);
        var secs = seconds % 60;
        return (mins < 10 ? "0" : "") + mins + ":" + (secs < 10 ? "0" : "") + secs;
    }

    // Update canvas when progress changes
    onProgressValueChanged: {
        progressCanvas.requestPaint();
    }
}