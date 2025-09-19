import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

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
    
    // Enhanced scaling properties for better 4K support
    property real baseSize: 400  // Base reference size
    property real scaleFactor: Math.min(width / baseSize, height / baseSize)
    property real timerSize: Math.min(width * 0.75, height * 0.75)  // More responsive to container size
    
    // Screen-aware scaling for different resolutions
    property real screenScale: {
        // var screenWidth = Screen.width || 1920  // Fallback to 1920 if Screen not available
        // 4k test
        // var screenWidth = 3840
        if (screenWidth >= 3840) return 1.3      // 4K - more reasonable scaling
        else if (screenWidth >= 2560) return 1.2  // 1440p
        else if (screenWidth >= 1920) return 1.0  // 1080p
        else return 0.8                           // Lower resolutions
    }
    
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
    readonly property color lightBlue: "#b3dcff" // Light purple-red closer to blue for last 10 seconds
    // readonly property color urgencyRed: "#df7466" // Light purple-red closer to blue for last 10 seconds
    // red 2 
    readonly property color urgencyRed: "#bd4e45" // Light purple-red closer to blue for last 10 seconds


    // readonly property color gradientColor1: Qt.rgba(0.08, 0.16, 0.29, 0.6) // #142849 with 60% alpha
    // readonly property color gradientColor2: Qt.rgba(0.42, 0.21, 0.15, 0.6) // #6b3527 with 60% alpha
    // readonly property color gradientColor3: Qt.rgba(0.71, 0.40, 0.23, 0.6) // #b5663b with 60% alpha
    // ========== GRADIENT COLORS FOR EASY MODIFICATION ==========
    // All states: Moving gradient effects with color variations
    // - ≤10 seconds: Light purple gradient (#B3B3FF) for urgency
    // - >10 seconds: Blue gradient (uclaBlue) for normal state
    // - Main progress circle: Flowing linear gradient
    // - Inner highlight: Moving gradient with lighter tones
    // - Progress dot: Radial gradient with enhanced variations
    // - Ripple effects: Color-coordinated with main theme
    // - Background ring: Matches main color scheme
    

   
    

    
    
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
            border.color: timerSeconds <= 10 ? urgencyRed : uclaBlue
            border.width: Math.max(4, 6 * scaleFactor)
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
            
            border.color: timerSeconds <= 10 ? urgencyRed : uclaBlue
            
            Behavior on border.color { ColorAnimation { duration: 300 } }
        }
        
        Rectangle {
            id: ripple2
            anchors.centerIn: parent
            width: 0; height: 0
            radius: width / 2
            color: "transparent"
            border.width: Math.max(2, 3 * scaleFactor)
            opacity: 0
            
            border.color: timerSeconds <= 10 ? Qt.lighter(urgencyRed, 1.2) : yinmnBlue
            
            Behavior on border.color { ColorAnimation { duration: 300 } }
        }
        
        Rectangle {
            id: ripple3
            anchors.centerIn: parent
            width: 0; height: 0
            radius: width / 2
            color: "transparent"
            border.width: Math.max(2, 3 * scaleFactor)
            opacity: 0
            
            border.color: timerSeconds <= 10 ? Qt.darker(urgencyRed, 1.1) : oxfordBlue2
            
            Behavior on border.color { ColorAnimation { duration: 300 } }
        }

        // Enhanced progress circle
        Canvas {
            id: progressCanvas
            anchors.fill: parent
            
            property real glowIntensity: isRunning ? 0.6 : 0.3
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
                var radius = (width - (20 * scaleFactor)) / 2;
                var startAngle = -Math.PI / 2;
                var progressAngle = (progressValue / 100) * 2 * Math.PI;
                
                // Background track
                ctx.beginPath();
                ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
                ctx.lineWidth = Math.max(8, 12 * scaleFactor);
                ctx.strokeStyle = Qt.rgba(0.1, 0.1, 0.2, 0.3);
                ctx.stroke();
                
                // Outer glow
                if (glowIntensity > 0) {
                    ctx.beginPath();
                    ctx.arc(centerX, centerY, radius + (4 * scaleFactor), startAngle, startAngle + progressAngle);
                    ctx.lineWidth = Math.max(6, 8 * scaleFactor);
                    ctx.strokeStyle = Qt.rgba(0.27, 0.45, 0.68, glowIntensity * 0.4);
                    ctx.stroke();
                }
                
                // Create gradient
                var gradient = ctx.createLinearGradient(
                    centerX - radius, centerY - radius, 
                    centerX + radius, centerY + radius
                );
                
                // Moving gradient effect for all states
                var time = Date.now() * 0.001; // Current time in seconds
                var gradientOffset = (time * 0.8) % 1.0; // Moving offset (0-1) - faster movement
                
                // Create a moving gradient with color variations based on timer state
                var baseColor, lighterColor, darkerColor, midColor;
                
                if (timerSeconds <= 10) {
                    // Red gradient for last 10 seconds - complementary to blue theme
                    baseColor = urgencyRed; // Soft red that complements blue
                    lighterColor = Qt.lighter(baseColor, 1.4);
                    darkerColor = Qt.darker(baseColor, 1.3);
                    midColor = Qt.lighter(baseColor, 1.1);
                } else {
                    // Blue gradient for normal states
                    baseColor = uclaBlue;
                    lighterColor = Qt.lighter(baseColor, 1.4);
                    darkerColor = Qt.darker(baseColor, 1.3);
                    midColor = Qt.lighter(baseColor, 1.1);
                }
                
                // Add color stops with moving positions for a flowing effect
                gradient.addColorStop((gradientOffset + 0.0) % 1.0, lighterColor);
                gradient.addColorStop((gradientOffset + 0.2) % 1.0, baseColor);
                gradient.addColorStop((gradientOffset + 0.4) % 1.0, midColor);
                gradient.addColorStop((gradientOffset + 0.6) % 1.0, darkerColor);
                gradient.addColorStop((gradientOffset + 0.8) % 1.0, baseColor);
                gradient.addColorStop((gradientOffset + 1.0) % 1.0, lighterColor);
                
                // Main progress arc
                ctx.beginPath();
                ctx.arc(centerX, centerY, radius, startAngle, startAngle + progressAngle);
                ctx.lineWidth = Math.max(12, 18 * scaleFactor);
                ctx.strokeStyle = gradient;
                ctx.lineCap = "round";
                ctx.stroke();
                
                // Inner highlight with moving gradient
                ctx.beginPath();
                ctx.arc(centerX, centerY, radius, startAngle, startAngle + progressAngle);
                ctx.lineWidth = Math.max(4, 6 * scaleFactor);
                
                // Create moving gradient for inner highlight
                var highlightGradient = ctx.createLinearGradient(
                    centerX - radius, centerY - radius, 
                    centerX + radius, centerY + radius
                );
                
                var highlightOffset = (time * 1.2) % 1.0; // Slightly faster movement for highlight
                var highlightBaseColor, highlightLighterColor, highlightDarkerColor;
                
                if (timerSeconds <= 10) {
                    // Red highlight for last 10 seconds
                    highlightBaseColor = Qt.lighter(urgencyRed, 1.6);
                    highlightLighterColor = Qt.lighter(highlightBaseColor, 1.3);
                    highlightDarkerColor = Qt.darker(highlightBaseColor, 1.2);
                } else {
                    // Blue highlight for normal states
                    highlightBaseColor = Qt.lighter(uclaBlue, 1.6);
                    highlightLighterColor = Qt.lighter(highlightBaseColor, 1.3);
                    highlightDarkerColor = Qt.darker(highlightBaseColor, 1.2);
                }
                
                highlightGradient.addColorStop((highlightOffset + 0.0) % 1.0, highlightLighterColor);
                highlightGradient.addColorStop((highlightOffset + 0.3) % 1.0, highlightBaseColor);
                highlightGradient.addColorStop((highlightOffset + 0.6) % 1.0, highlightDarkerColor);
                highlightGradient.addColorStop((highlightOffset + 0.9) % 1.0, highlightBaseColor);
                
                ctx.strokeStyle = highlightGradient;
                ctx.lineCap = "round";
                ctx.stroke();
                
                // Progress indicator dot with moving gradient
                if (progressAngle > 0.1) {
                    var dotX = centerX + radius * Math.cos(startAngle + progressAngle);
                    var dotY = centerY + radius * Math.sin(startAngle + progressAngle);
                    
                    // Create moving gradient for dot
                    var dotGradient = ctx.createRadialGradient(
                        dotX - Math.max(2, 3 * scaleFactor), dotY - Math.max(2, 3 * scaleFactor), 0,
                        dotX, dotY, Math.max(4, 6 * scaleFactor)
                    );
                    
                    var dotOffset = (time * 1.5) % 1.0; // Fast movement for dot
                    var dotBaseColor, dotLighterColor, dotDarkerColor, dotCenterColor;
                    
                    if (timerSeconds <= 10) {
                        // Red dot for last 10 seconds
                        dotBaseColor = urgencyRed;
                        dotLighterColor = Qt.lighter(dotBaseColor, 1.5);
                        dotDarkerColor = Qt.darker(dotBaseColor, 1.3);
                        dotCenterColor = Qt.lighter(dotBaseColor, 1.2);
                    } else {
                        // Blue dot for normal states
                        dotBaseColor = uclaBlue;
                        dotLighterColor = Qt.lighter(dotBaseColor, 1.5);
                        dotDarkerColor = Qt.darker(dotBaseColor, 1.3);
                        dotCenterColor = Qt.lighter(dotBaseColor, 1.2);
                    }
                    
                    // Create radial gradient with moving colors
                    dotGradient.addColorStop(0.0, dotLighterColor);
                    dotGradient.addColorStop(0.3, dotCenterColor);
                    dotGradient.addColorStop(0.7, dotBaseColor);
                    dotGradient.addColorStop(1.0, dotDarkerColor);
                    
                    // Outer dot with moving gradient
                    ctx.beginPath();
                    ctx.arc(dotX, dotY, Math.max(4, 6 * scaleFactor), 0, 2 * Math.PI);
                    ctx.fillStyle = dotGradient;
                    ctx.fill();
                    
                    // Inner dot with enhanced color
                    ctx.beginPath();
                    ctx.arc(dotX, dotY, Math.max(2, 3 * scaleFactor), 0, 2 * Math.PI);
                    ctx.fillStyle = Qt.lighter(dotBaseColor, 1.4);
                    ctx.fill();
                    
                    // Add a small white highlight for extra shine
                    ctx.beginPath();
                    ctx.arc(dotX - Math.max(1, 1.5 * scaleFactor), dotY - Math.max(1, 1.5 * scaleFactor), 
                           Math.max(1, 1.5 * scaleFactor), 0, 2 * Math.PI);
                    ctx.fillStyle = Qt.rgba(1, 1, 1, 0.8);
                    ctx.fill();
                }
            }
        }

        // Timer for moving gradient animation (active for all states)
        Timer {
            id: gradientAnimationTimer
            interval: 50 // Update every 50ms for smooth animation
            running: isRunning
            repeat: true
            onTriggered: {
                progressCanvas.requestPaint();
            }
        }

        // Timer text display
        Text {
            id: timerText
            text: formatTime(timerSeconds)
            font.family: customFontLoader.name
            font.pixelSize: Math.max(24, 48 * scaleFactor)
            font.bold: true
            // color: timerSeconds <= 10 ? oxfordBlue2 : yinmnBlue
            // color: timerSeconds <= 10 ? urgencyRed : lightBlue
            color: timerSeconds <= 10 ? urgencyRed : Qt.lighter(uclaBlue, 1.5)
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
        // Text {
        //     id: statusText
        //     text: isRunning ? "RUNNING - Press 'S' to Stop" : "READY - Press 'S' to Start"
        //     font.family: customFontLoader.name
        //     font.pixelSize: Math.max(8, 12 * scaleFactor)
        //     font.bold: true
        //     color: isRunning ? uclaBlue : yinmnBlue
        //     anchors.horizontalCenter: parent.horizontalCenter
        //     anchors.top: timerText.bottom
        //     anchors.topMargin: 10 * scaleFactor
            
        //     renderType: Text.NativeRendering
        //     antialiasing: true
            
        //     SequentialAnimation on opacity {
        //         loops: Animation.Infinite
        //         running: isRunning
        //         NumberAnimation { from: 0.7; to: 1.0; duration: 800 }
        //         NumberAnimation { from: 1.0; to: 0.7; duration: 800 }
        //     }
        // }
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
                to: 1.2
                duration: 150
                easing.type: Easing.OutQuad
            }
            NumberAnimation {
                target: textScale
                properties: "xScale,yScale"
                to: 1.0
                duration: 250
                easing.type: Easing.OutElastic
            }
        }
        
        SequentialAnimation {
            ColorAnimation {
                target: timerText
                property: "color"
                from: "white"
                to: {
                    if (timerSeconds <= 30) return uclaBlue;
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
                to: 3
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
            PauseAnimation { duration: 0 }
            ParallelAnimation {
                NumberAnimation {
                    target: ripple1
                    properties: "width,height"
                    from: 0
                    to: timerSize * 1.0
                    duration: 800
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: ripple1
                    property: "opacity"
                    from: 0.7
                    to: 0
                    duration: 800
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
            PauseAnimation { duration: 120 }
            ParallelAnimation {
                NumberAnimation {
                    target: ripple2
                    properties: "width,height"
                    from: 0
                    to: timerSize * 1.15
                    duration: 800
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: ripple2
                    property: "opacity"
                    from: 0.7
                    to: 0
                    duration: 800
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
            PauseAnimation { duration: 240 }
            ParallelAnimation {
                NumberAnimation {
                    target: ripple3
                    properties: "width,height"
                    from: 0
                    to: timerSize * 1.3
                    duration: 800
                    easing.type: Easing.OutCubic
                }
                NumberAnimation {
                    target: ripple3
                    property: "opacity"
                    from: 0.7
                    to: 0
                    duration: 800
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
