mkdir venv
python3 -m venv venv
venv/bin/pip install pyinstaller
venv/bin/pip install tqdm
venv/bin/pyinstaller --noconfirm --onefile --console "Client/client.py"
venv/bin/pyinstaller --noconfirm --onefile --console "Server/server.py"
rm -rf build
rm -rf venv
rm client.spec
rm server.spec
