# Smart Expense Tracker with Graphical Analytics

A full-stack web application developed using **Python Flask and MySQL** to manage personal income, expenses, and monthly budgets. The application provides graphical financial analytics, transaction management, and secure user authentication.

## Features

- User Registration and Login
- Secure Password Hashing
- Dashboard with Financial Summaries
- Add, Edit, and Delete Transactions
- Monthly Budget Management
- Reports and Graphical Analytics
- Search and Filter Transactions
- CSV and PDF Report Export
- Profile Management
- Change Password
- Multi-user Data Isolation
- CSRF Protection and Login Rate Limiting

## Technologies Used

**Backend**
- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-WTF

**Frontend**
- HTML5
- CSS3
- Bootstrap 5
- JavaScript
- Chart.js

**Database**
- MySQL

## Project Setup

### 1. Clone the Repository

```bash
git clone https://github.com/Sooraj6381/Smart-Expense-Tracker.git
cd Smart-Expense-Tracker
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

### 3. Activate the Virtual Environment

**Windows PowerShell:**

```powershell
venv\Scripts\Activate
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the project root directory.

Add the following configuration:

```env
SECRET_KEY=your_random_secret_key

DATABASE_URL=mysql+pymysql://username:password@localhost:3306/smart_expense_tracker

FLASK_DEBUG=0
```

Replace the example values with your own configuration. URL-encode special characters in your database password when necessary.

### 6. Configure MySQL

Create the database in MySQL:

```sql
CREATE DATABASE smart_expense_tracker;
```

Configure your MySQL credentials in the `.env` file.

### 7. Run the Application

```bash
python app.py
```

### 8. Open in Browser

Visit:

http://127.0.0.1:5000

## Security

- Passwords are securely hashed.
- CSRF protection is enabled.
- Login attempts are rate-limited.
- User data is isolated between accounts.
- Sensitive configuration is stored in environment variables.
- The `.env` file is excluded from Git tracking.

**Important:** Never upload database passwords, secret keys, or private user data to GitHub.

## Developer

**Sooraj L J**

Full Stack Python Developer

GitHub: [Sooraj6381](https://github.com/Sooraj6381)