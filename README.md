PP2LA CW Interface & Keyer

This project consists of a Graphical User Interface (GUI) developed in Python for controlling Morse Code (CW) transmission via Arduino. The system allows for free-text typing, macro usage, speed control (WPM), automated Auto CQ, and contact logging (Logbook) in ADIF format.

==================================================
FEATURES
==================================================

- Hybrid Keyer: Sends CW typed in real-time or via Macros.
- Serial Control: Robust communication with Arduino via USB.
- Integrated Logbook: Automatically saves contacts in the worldwide standard ADIF format (.adi), compatible with QRZ, LoTW, eQSL, etc.
- Configurable Auto CQ: Automatic calling loop with adjustable timer.
- CW Dictionary: Quick reference for abbreviations and Q-codes.
- Hotkeys: Keyboard shortcuts (F1–F12, ESC, PageUp/Down) for fast operation during contests or DXing.

==================================================
HARDWARE (ARDUINO)
==================================================

The Arduino firmware acts as a serial buffer that translates ASCII characters into precise Morse timing pulses.

Wiring Diagram

The system uses Arduino digital pin 8 to key the radio.

- Arduino Pin 8: Key Signal (Radio Connector Tip).
- Arduino GND: Radio Ground (Radio Connector Sleeve/Shell).

IMPORTANT:
It is highly recommended to use an optocoupler (e.g., 4N25, PC817) or a transistor to isolate the PC from the radio, preventing ground loops or damage to the USB port.

Example with Optocoupler:

1. Arduino Pin 8 -> 220 ohm resistor -> Optocoupler Anode (Pin 1).
2. Arduino GND -> Optocoupler Cathode (Pin 2).
3. Opto Emitter (Pin 4) -> Radio GND (Key -).
4. Opto Collector (Pin 5) -> Radio Tip (Key +).

Firmware Upload

1. Open the CWarduino.ino file in the Arduino IDE.
2. Select your board (Uno, Nano, etc.).
3. Upload the code.

==================================================
SOFTWARE (PYTHON)
==================================================

The interface was built using native tkinter, ensuring it is lightweight and compatible across platforms.

Prerequisites

You must have Python installed. The only external library required is pyserial for communication with the Arduino.

Installation command:

pip install pyserial

How to Run

Run the main script:

python CWinterface.py

==================================================
COMMUNICATION PROTOCOL
==================================================

Communication between Python and Arduino occurs via Serial (Baud Rate: 9600).

1. Text Transmission:
Any string sent ending with a newline character (\n) will be interpreted by the Arduino, converted to Morse, and transmitted.

2. Speed Command:
The command /wpm N (where N is a number) adjusts the transmission speed instantly.
Example: /wpm 25 sets the speed to 25 WPM.

==================================================
USER MANUAL
==================================================

1. Initial Connection

1. In the OPERAÇÃO (Operation) tab, click the reload button (⟳) to list available COM ports.
2. Select the Arduino port and click Conectar (Connect).
3. The status will appear in the Terminal (e.g., [SYS] Conectado: COM3).

2. Station Setup

Fill in the Call (Callsign), Nome (Name), and Grid fields in the Dados da Estação section.
Click Salvar (Save). These details are automatically used in Macros (for example, F1 uses the saved callsign).

3. Operation (TX)

- Terminal: Type in the bottom text field and press ENTER. The text will be sent to the Arduino.
- Speed: Use the number box or the PageUp / PageDown keys to change the WPM between 1 and 50.
- Stop (Panic): Press ESC at any time to interrupt Auto CQ or stop sending a long message.

4. Macros and Auto CQ

- F1 – F12: Send pre-configured messages. Use the EDITAR MACROS button to customize them.
- Auto CQ: Set an interval time in seconds (default is 15 seconds) and click AUTO CQ.
  The system will send the F1 macro in a loop until clicked again or interrupted with ESC.

5. Logbook

1. During a QSO, fill in DX CALL, RST Sent/Received, Band, and Frequency.
2. Press CTRL + ENTER or click LOGAR.
3. The contact is automatically saved to the logbook.adi file.
4. View history in the LOGBOOK tab, where you can filter by band.

Macro Variables

When editing your macros, you can use the following placeholders, which are replaced automatically:

- {call}: Your callsign.
- {name}: Your name.
- {grid}: Your grid locator.
- {target}: DX callsign (from the DX CALL field).
- {rst}: RST sent (the system automatically converts 599 to 5NN when sending).

==================================================
HOTKEYS
==================================================

F1 – F12        : Send corresponding macros
ESC             : Stop transmission / Cancel Auto CQ
CTRL + ENTER    : Save contact to Logbook
PAGE UP         : Increase speed (+2 WPM)
PAGE DOWN       : Decrease speed (-2 WPM)

==================================================
LICENSE
==================================================

This project was developed as an open-source tool for amateur radio operators.
Feel free to modify and improve it.

Author: Lucas (PP2LA)
