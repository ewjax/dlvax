run:
	py DeathLoopVaccine.py

setup: requirements.txt
	pip install -r requirements.txt

exe: DeathLoopVaccine.py EverquestLogFile.py
	pyinstaller --onefile --icon data/icons/DeathLoopVaccine.ico DeathLoopVaccine.py

zip:
	cp DeathLoopVaccine.ini.example dist
	cd dist && zip DeathLoopVaccine.zip DeathLoopVaccine.exe DeathLoopVaccine.ini.example

clean:
	rm dist/DeathLoopVaccine.exe
	rm dist/DeathLoopVaccine.ini.example
	rm dist/DeathLoopVaccine.zip



