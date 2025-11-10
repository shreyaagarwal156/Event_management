# Event_management

GEU Events - MySQL Project Setup
These instructions are for running the app.py file with your local MySQL server.

Step 1: Create the Database in MySQL Workbench

Open your MySQL Workbench and log in to your local connection.

Open a new query tab and run only this one command:

SQL

CREATE DATABASE event_system;
IMPORTANT: You do not need to run the database.sql file (which contains the CREATE TABLE statements). app.py will handle this automatically.

Step 2: Set Up the Project in Terminal

Open your Windows Terminal and navigate to the project folder:

Bash

cd Desktop\Event_Management
Create a virtual environment (if it doesn't already exist):

Bash

python -m venv venv
Activate the environment:

Bash

.\venv\Scripts\activate
(You should see (venv) at the beginning of your prompt.)

Step 3: Install All Libraries

While (venv) is active, run this command:

Bash

pip install Flask Flask-SQLAlchemy Flask-Cors Flask-Bcrypt PyJWT PyMySQL
(PyMySQL is the driver that allows Python to communicate with MySQL.)

Step 4: Run the Server

After the libraries are installed, run the server:

Bash

python app.py
You should see this in your terminal (without any red errors):

Default admin user (admin@geu.ac.in / admin123) created.
Default 'GEU Auditorium' venue created.
Database tables checked and initial data added.
 * Running on http://127.0.0.1:5000/
Open your browser and go to http://127.0.0.1:5000/.

Your complete advanced application is ready!
