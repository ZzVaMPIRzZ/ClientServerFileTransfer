mkdir venv
python3 -m venv venv
# venv/bin/pip install auto-py-to-exe
# venv/bin/auto-py-to-exe
sudo apt-get install libxcb-xinerama0 libxcb1 libxcb-util1 libx11-xcb1 libxrender1 libxi6
venv/bin/pip install pyinstaller
venv/bin/pip install tqdm
venv/bin/pip install PyQt5
venv/bin/pyinstaller --noconfirm --onefile --console "src/Client.py"
venv/bin/pyinstaller --noconfirm --onefile --console "src/Server.py"
venv/bin/pyinstaller --noconfirm --onefile --windowed "src/ClientGUI.py"
rm -rf build
rm -rf venv
rm Client.spec
rm Server.spec
rm ClientGUI.spec
