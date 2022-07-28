run:
	py DeathLoopVaccine.py

setup: requirements.txt
	pip install -r requirements.txt

exe: DeathLoopVaccine.py EverquestLogFile.py
	pyinstaller --onefile --icon data/icons/icons8-vaccination-64a.ico DeathLoopVaccine.py

clean:
	rm ./__pycache__/*.*


