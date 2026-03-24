Mechanic's CyberKnife: Diagnostic OS
Mechanic's CyberKnife is an immersive, high-fidelity diagnostic operating system designed for vehicle technicians and automotive enthusiasts. Built with a retro-futuristic "Cyber-3000" aesthetic, it bridges the gap between hardware-level automotive data and a touch-optimized, interactive user experience.
🛠 Core Features
 * Real-Time Data Visualization: High-precision gauges and a live data strip track 22+ sensor parameters, including RPM, MAP, AFR, and Knock Retard, with sub-millisecond responsiveness.
 * Professional Diagnostic Suite:
   * CAN/LIN Bus Analyzer: Real-time packet capturing and anomaly detection for modern vehicle networks.
   * Oscilloscope & Multimeter: A full-screen oscilloscope and a multi-mode Power Probe (BAT+, GND, Continuity, PWM) for electrical circuit testing.
   * OBD-II & UDS Integration: Support for PID requests and advanced UDS services like Security Access and EEPROM read/write.
 * ECU Tuning & Maps: Interactive 9x12 2D grids for Volumetric Efficiency (VE), Ignition Advance, and AFR target mapping.
 * AI-Driven Coaching (Cyber Boy): A reactive, animated assistant that provides contextual advice, detects engine faults, and offers technical guidance through an "Ask Cyber Boy" FAQ system.
 * Advanced Visual Tools: Simulated thermal camera heat mapping for exhaust gas temperature (EGT) and borescope cylinder inspection views.
💻 Architecture
 * Tech Stack: Pure HTML5, CSS3, and Vanilla JavaScript (No heavy frameworks, ensuring 60fps performance on mobile devices).
 * Rendering: High-performance canvas rendering via requestAnimationFrame (RAF) and a centralized event bus (CKBus) for decoupled subsystem communication.
 * Hardware Interface: Integrated WebSerial API layer for direct communication with real-world ECU hardware while maintaining a robust internal physics simulation for offline learning.
🚀 Getting Started
 * Clone the Repository: git clone https://github.com/your-repo/cyberknife.git
 * Launch: Open the latest cyberknife_vX.X.html file in any modern web browser.
 * Operation: Use the rotary "Knob Zone" or main navigation bar to switch between Diagnostic, Data, and Tuning modes.
 * Hardware Connection: Toggle the Hardware dot in the top bar to connect via WebSerial for real vehicle data.
📜 Development Philosophy
This project is built for the "fat-finger" environment of a real garage, featuring large touch targets (≥44px) and high-contrast neon visuals designed for visibility under shop lights.
Developed by a mechanic, for mechanics.
