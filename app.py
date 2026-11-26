from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import (Flask,render_template,request,redirect,url_for,flash,make_response,send_file)
from dotenv import load_dotenv
from flask_login import (login_user,logout_user,login_required,current_user)
from extensions import db, login_manager, csrf
from models import User, Transaction, Budget
from sqlalchemy import func
import os
import re


# STEP 1: Load environment variables
load_dotenv()


# STEP 2: Create Flask application
app = Flask(__name__)


# STEP 3: Application configuration

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

if not app.config["SECRET_KEY"]:
    raise RuntimeError(
        "SECRET_KEY is missing. Please configure it in your .env file."
    )

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")

if not app.config["SQLALCHEMY_DATABASE_URI"]:
    raise RuntimeError(
        "DATABASE_URL is missing. Please check your .env file."
    )

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Session Security Settings
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Login Attempt Protection
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[]
)


# STEP 4: Initialize Flask extensions
db.init_app(app)
login_manager.init_app(app)
csrf.init_app(app)

login_manager.login_view = "login"


# STEP 5: Load logged-in user
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# STEP 6: Home route
@app.route("/")
def home():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))



# STEP 7: Registration route
@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        # Check empty fields
        if not name or not email or not password:
            flash("Please fill in all fields.", "danger")
            return render_template("register.html")

        # Validate email format
        email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

        if not re.fullmatch(email_pattern, email):
            flash("Please enter a valid email address.", "danger")
            return render_template("register.html")

        # Validate password length
        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "danger")
            return render_template("register.html")

        # Check existing email
        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("Email address is already registered.", "danger")
            return render_template("register.html")

        # Create new user
        new_user = User(
            name=name,
            email=email
        )

        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please login.", "success")

        return redirect(url_for("login"))

    return render_template("register.html")


# STEP 8: Login route
@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():

    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):

            login_user(user)

            flash("Welcome back!", "success")

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


# STEP 9: Dashboard route
@app.route("/dashboard")
@login_required
def dashboard():

    from datetime import datetime

    # Current month and year
    current_month = datetime.now().month
    current_year = datetime.now().year

    # Total income
    total_income = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter_by(
        user_id=current_user.id,
        type="income"
    ).scalar()

    # Total expenses
    total_expenses = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter_by(
        user_id=current_user.id,
        type="expense"
    ).scalar()

    # Balance
    balance = total_income - total_expenses

    # Latest 5 transactions
    recent_transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.date.desc(),
        Transaction.id.desc()
    ).limit(5).all()

    # Expense categories
    category_data = db.session.query(
        Transaction.category,
        func.sum(Transaction.amount)
    ).filter_by(
        user_id=current_user.id,
        type="expense"
    ).group_by(
        Transaction.category
    ).all()

    category_labels = [
        item[0] for item in category_data
    ]

    category_values = [
        float(item[1]) for item in category_data
    ]

    # Monthly budget progress
    monthly_budgets = Budget.query.filter_by(
        user_id=current_user.id,
        month=current_month,
        year=current_year
    ).all()

    budget_progress = []

    for budget in monthly_budgets:

        spent = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter_by(
            user_id=current_user.id,
            category=budget.category,
            type="expense"
        ).filter(
            func.month(Transaction.date) == current_month,
            func.year(Transaction.date) == current_year
        ).scalar()

        percentage = (
            float(spent / budget.limit * 100)
            if budget.limit > 0 else 0
        )

        budget_progress.append({
            "category": budget.category,
            "limit": budget.limit,
            "spent": spent,
            "remaining": max(budget.limit - spent, 0),
            "percentage": percentage
        })

    return render_template(
        "dashboard.html",
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        recent_transactions=recent_transactions,
        category_labels=category_labels,
        category_values=category_values,
        budget_progress=budget_progress
    )


# STEP 10: Logout route
@app.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()

    flash("You have been logged out successfully.", "success")

    return redirect(url_for("login"))


# STEP 12: Profile Management
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("profile"))

        # Check whether another user already uses this email
        existing_user = User.query.filter(
            User.email == email,
            User.id != current_user.id
        ).first()

        if existing_user:
            flash("This email is already registered.", "danger")
            return redirect(url_for("profile"))

        current_user.name = name
        current_user.email = email

        db.session.commit()

        flash("Profile updated successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html")


# STEP 13: Change Password
@app.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():

    if request.method == "POST":

        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not current_user.check_password(current_password):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("change_password"))

        if len(new_password) < 8:
            flash("New password must contain at least 8 characters.", "danger")
            return redirect(url_for("change_password"))

        if new_password != confirm_password:
            flash("New passwords do not match.", "danger")
            return redirect(url_for("change_password"))

        current_user.set_password(new_password)

        db.session.commit()

        flash("Password changed successfully!", "success")
        return redirect(url_for("profile"))

    return render_template("change_password.html")


# STEP 11: Transactions page with Search, Filters and Pagination
@app.route("/transactions")
@login_required
def transactions():

    search = request.args.get("search", "").strip()
    transaction_type = request.args.get("type", "").strip()
    category = request.args.get("category", "").strip()
    date = request.args.get("date", "").strip()

    # Get current page number
    page = request.args.get("page", 1, type=int)

    query = Transaction.query.filter_by(
        user_id=current_user.id
    )

    # Search by description
    if search:
        query = query.filter(
            Transaction.description.ilike(f"%{search}%")
        )

    # Filter by transaction type
    if transaction_type in ["income", "expense"]:
        query = query.filter_by(type=transaction_type)

    # Filter by category
    if category:
        query = query.filter_by(category=category)

    # Filter by date
    if date:
        try:
            from datetime import datetime
            selected_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(Transaction.date == selected_date)
        except ValueError:
            pass

    # Order transactions by latest date
    query = query.order_by(
        Transaction.date.desc(),
        Transaction.id.desc()
    )

    # Pagination: 10 transactions per page
    pagination = query.paginate(
        page=page,
        per_page=10,
        error_out=False
    )

    # Get available categories
    categories = db.session.query(
        Transaction.category
    ).filter_by(
        user_id=current_user.id
    ).distinct().order_by(
        Transaction.category
    ).all()

    return render_template(
        "transactions.html",
        transactions=pagination.items,
        pagination=pagination,
        categories=[item[0] for item in categories]
    )


# STEP 12: Add transaction
@app.route("/add-transaction", methods=["GET", "POST"])
@login_required
def add_transaction():

    from datetime import datetime
    from decimal import Decimal, InvalidOperation

    if request.method == "POST":

        description = request.form.get("description", "").strip()
        amount_value = request.form.get("amount", "")
        transaction_type = request.form.get("type", "")
        category = request.form.get("category", "").strip()
        transaction_date = request.form.get("date", "")

        if not all([
            description,
            amount_value,
            transaction_type,
            category,
            transaction_date
        ]):
            flash("Please fill in all fields.", "danger")
            return render_template("transaction_form.html")

        if transaction_type not in ["income", "expense"]:
            flash("Invalid transaction type.", "danger")
            return render_template("transaction_form.html")

        try:
            amount = Decimal(amount_value)

            if not amount.is_finite() or amount <= 0:
                raise InvalidOperation

            parsed_date = datetime.strptime(
                transaction_date,
                "%Y-%m-%d"
            ).date()

            new_transaction = Transaction(
                description=description,
                amount=amount,
                type=transaction_type,
                category=category,
                date=parsed_date,
                user_id=current_user.id
            )

            db.session.add(new_transaction)
            db.session.commit()

            flash("Transaction added successfully!", "success")

            return redirect(url_for("dashboard"))

        except (InvalidOperation, ValueError):
            db.session.rollback()
            flash("Enter a valid amount and date.", "danger")

    return render_template("transaction_form.html")


# STEP 13: Budget management
@app.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():

    from datetime import datetime
    from decimal import Decimal, InvalidOperation

    current_month = datetime.now().month
    current_year = datetime.now().year

    if request.method == "POST":

        category = request.form.get("category", "").strip()
        limit_value = request.form.get("limit", "").strip()

        try:
            budget_limit = Decimal(limit_value)

            if not budget_limit.is_finite() or not category or budget_limit <= 0:
                flash("Enter a category and a valid budget limit.", "danger")
                return redirect(url_for("budgets"))

        except (InvalidOperation, ValueError):
            flash("Please enter a valid budget amount.", "danger")
            return redirect(url_for("budgets"))

        existing_budget = Budget.query.filter_by(
            user_id=current_user.id,
            category=category,
            month=current_month,
            year=current_year
        ).first()

        if existing_budget:
            existing_budget.limit = budget_limit
            flash("Budget updated successfully!", "success")

        else:
            new_budget = Budget(
                category=category,
                limit=budget_limit,
                month=current_month,
                year=current_year,
                user_id=current_user.id
            )

            db.session.add(new_budget)
            flash("Budget created successfully!", "success")

        db.session.commit()

        return redirect(url_for("budgets"))

    budgets_list = Budget.query.filter_by(
        user_id=current_user.id,
        month=current_month,
        year=current_year
    ).all()

    for budget in budgets_list:

        budget.spent = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.category == budget.category,
            Transaction.type == "expense",
            func.month(Transaction.date) == current_month,
            func.year(Transaction.date) == current_year
        ).scalar()

    # Budget summary calculations
    total_budget = sum(
        (Decimal(str(budget.limit or 0)) for budget in budgets_list),
        Decimal("0")
    )

    total_spent = sum(
        (Decimal(str(budget.spent or 0)) for budget in budgets_list),
        Decimal("0")
    )

    remaining_budget = total_budget - total_spent

    return render_template(
        "budgets.html",
        budgets=budgets_list,
        total_budget=total_budget,
        total_spent=total_spent,
        remaining_budget=remaining_budget
    )


# STEP 14: Edit budget
@app.route("/edit_budget/<int:budget_id>", methods=["GET", "POST"])
@login_required
def edit_budget(budget_id):

    from decimal import Decimal, InvalidOperation

    budget = Budget.query.filter_by(
        id=budget_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":

        category = request.form.get("category", "").strip()
        limit_value = request.form.get("limit", "").strip()

        try:
            budget_limit = Decimal(limit_value)

            if (
                not budget_limit.is_finite()
                or not category
                or budget_limit <= 0
            ):
                flash("Enter a valid category and budget limit.", "danger")
                return redirect(
                    url_for("edit_budget", budget_id=budget.id)
                )

        except (InvalidOperation, ValueError):
            flash("Please enter a valid budget amount.", "danger")
            return redirect(
                url_for("edit_budget", budget_id=budget.id)
            )

        budget.category = category
        budget.limit = budget_limit

        db.session.commit()

        flash("Budget updated successfully!", "success")

        return redirect(url_for("budgets"))

    return render_template(
        "edit_budget.html",
        budget=budget
    )


# STEP 15: Delete budget
@app.route("/delete-budget/<int:budget_id>", methods=["POST"])
@login_required
def delete_budget(budget_id):

    budget = Budget.query.filter_by(
        id=budget_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(budget)
    db.session.commit()

    flash("Budget deleted successfully!", "success")

    return redirect(url_for("budgets"))


# STEP 16: Edit transaction
@app.route("/edit-transaction/<int:transaction_id>", methods=["GET", "POST"])
@login_required
def edit_transaction(transaction_id):

    from datetime import datetime
    from decimal import Decimal, InvalidOperation

    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":

        description = request.form.get("description", "").strip()
        amount_value = request.form.get("amount", "")
        transaction_type = request.form.get("type", "")
        category = request.form.get("category", "").strip()
        transaction_date = request.form.get("date", "")

        if not all([
            description,
            amount_value,
            transaction_type,
            category,
            transaction_date
        ]):
            flash("Please fill in all fields.", "danger")

        elif transaction_type not in ["income", "expense"]:
            flash("Invalid transaction type.", "danger")

        else:

            try:
                amount = Decimal(amount_value)

                if not amount.is_finite() or amount <= 0:
                    raise InvalidOperation

                parsed_date = datetime.strptime(
                    transaction_date,
                    "%Y-%m-%d"
                ).date()

                transaction.description = description
                transaction.amount = amount
                transaction.type = transaction_type
                transaction.category = category
                transaction.date = parsed_date

                db.session.commit()

                flash("Transaction updated successfully!", "success")

                return redirect(url_for("transactions"))

            except (InvalidOperation, ValueError):
                db.session.rollback()
                flash("Enter a valid amount and date.", "danger")

    return render_template(
        "edit_transaction.html",
        transaction=transaction
    )


# STEP 17: Delete transaction
@app.route("/delete-transaction/<int:transaction_id>", methods=["POST"])
@login_required
def delete_transaction(transaction_id):

    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=current_user.id
    ).first_or_404()

    db.session.delete(transaction)
    db.session.commit()

    flash("Transaction deleted successfully!", "success")

    return redirect(url_for("transactions"))


# STEP 18: Reports and Analytics
@app.route("/reports")
@login_required
def reports():

    from datetime import datetime

    current_month = datetime.now().month
    current_year = datetime.now().year

    try:
        selected_month = int(
            request.args.get("month", current_month)
        )

        selected_year = int(
            request.args.get("year", current_year)
        )

        if not 1 <= selected_month <= 12:
            raise ValueError

        if not 2000 <= selected_year <= 2100:
            raise ValueError

    except (ValueError, TypeError):
        flash("Invalid month or year selected.", "danger")
        return redirect(url_for("reports"))

    month_filter = func.month(Transaction.date) == selected_month
    year_filter = func.year(Transaction.date) == selected_year

    # Monthly income
    total_income = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "income",
        month_filter,
        year_filter
    ).scalar()

    # Monthly expenses
    total_expenses = db.session.query(
        func.coalesce(func.sum(Transaction.amount), 0)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        month_filter,
        year_filter
    ).scalar()

    # Monthly balance
    balance = total_income - total_expenses

    # Category-wise expenses
    category_data = db.session.query(
        Transaction.category,
        func.sum(Transaction.amount)
    ).filter(
        Transaction.user_id == current_user.id,
        Transaction.type == "expense",
        month_filter,
        year_filter
    ).group_by(
        Transaction.category
    ).all()

    category_labels = [
        item[0] for item in category_data
    ]

    category_values = [
        float(item[1]) for item in category_data
    ]

    return render_template(
        "reports.html",
        total_income=total_income,
        total_expenses=total_expenses,
        balance=balance,
        category_labels=category_labels,
        category_values=category_values,
        selected_month=selected_month,
        selected_year=selected_year
    )



# STEP 19: Export transactions as CSV
@app.route("/export-csv")
@login_required
def export_csv():

    import csv
    import io

    # Protect text fields from spreadsheet formula injection
    def safe_csv_value(value):

        if value is None:
            return ""

        value = str(value)

        if value.lstrip().startswith(("=", "+", "-", "@")):
            value = "'" + value

        return value

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Date",
        "Description",
        "Category",
        "Type",
        "Amount"
    ])

    transactions = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.date.desc()
    ).all()

    for transaction in transactions:

        writer.writerow([
            transaction.date,
            safe_csv_value(transaction.description),
            safe_csv_value(transaction.category),
            safe_csv_value(transaction.type),
            transaction.amount
        ])

    response = make_response(output.getvalue())

    response.headers["Content-Disposition"] = (
        "attachment; filename=smart_expense_report.csv"
    )

    response.headers["Content-Type"] = "text/csv; charset=utf-8"

    return response



# STEP 20: Export monthly report as PDF
@app.route("/export-pdf")
@login_required
def export_pdf():

    import io
    import calendar
    from xml.sax.saxutils import escape
    from datetime import datetime
    from decimal import Decimal

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle)
    from reportlab.lib.enums import TA_LEFT

    # Validate selected month and year
    try:
        selected_month = int(
            request.args.get("month", datetime.now().month)
        )

        selected_year = int(
            request.args.get("year", datetime.now().year)
        )

        if not 1 <= selected_month <= 12:
            raise ValueError

        if not 2000 <= selected_year <= 2100:
            raise ValueError

    except (ValueError, TypeError):
        flash("Invalid month or year selected.", "danger")
        return redirect(url_for("reports"))

    # Get selected month's transactions
    transactions = Transaction.query.filter(
        Transaction.user_id == current_user.id,
        func.month(Transaction.date) == selected_month,
        func.year(Transaction.date) == selected_year
    ).order_by(
        Transaction.date.desc(),
        Transaction.id.desc()
    ).all()

    # Calculate monthly totals
    total_income = sum(
        (t.amount for t in transactions if t.type == "income"),
        Decimal("0")
    )

    total_expenses = sum(
        (t.amount for t in transactions if t.type == "expense"),
        Decimal("0")
    )

    balance = total_income - total_expenses

    # Calculate category-wise expenses
    category_totals = {}

    for transaction in transactions:

        if transaction.type == "expense":

            category_totals[transaction.category] = (
                category_totals.get(
                    transaction.category,
                    Decimal("0")
                ) + transaction.amount
            )

    # Create PDF in memory
    pdf_buffer = io.BytesIO()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )

    styles = getSampleStyleSheet()
    elements = []

    # PDF title
    elements.append(
        Paragraph(
            "Smart Expense Tracker",
            styles["Title"]
        )
    )

    elements.append(
        Paragraph(
            f"Monthly Financial Report - "
            f"{calendar.month_name[selected_month]} {selected_year}",
            styles["Heading2"]
        )
    )

    elements.append(
        Paragraph(
            f"Prepared for: {escape(str(current_user.name))}",
            styles["Normal"]
        )
    )

    elements.append(Spacer(1, 20))

    # Financial summary
    elements.append(
        Paragraph(
            "Financial Summary",
            styles["Heading2"]
        )
    )

    summary_data = [
        ["Description", "Amount"],
        ["Total Income", f"Rs. {total_income:,.2f}"],
        ["Total Expenses", f"Rs. {total_expenses:,.2f}"],
        ["Remaining Balance", f"Rs. {balance:,.2f}"]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[3.5 * inch, 2.5 * inch]
    )

    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")
    ]))

    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # Category-wise expenses
    elements.append(
        Paragraph(
            "Category-wise Expenses",
            styles["Heading2"]
        )
    )

    category_data = [
        ["Category", "Amount"]
    ]

    for category, amount in category_totals.items():

        category_data.append([
            Paragraph(escape(str(category)), styles["BodyText"]),
            f"Rs. {amount:,.2f}"
        ])

    if not category_totals:
        category_data.append([
            "No expenses",
            "Rs. 0.00"
        ])

    category_table = Table(
        category_data,
        colWidths=[3.5 * inch, 2.5 * inch]
    )

    category_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 8)
    ]))

    elements.append(category_table)
    elements.append(Spacer(1, 20))

    # Transaction history
    elements.append(
        Paragraph(
            "Transaction History",
            styles["Heading2"]
        )
    )

    transaction_data = [
        ["Date", "Description", "Category", "Type", "Amount"]
    ]

    for transaction in transactions:

        transaction_data.append([
            transaction.date.strftime("%d-%m-%Y"),
            Paragraph(
                escape(str(transaction.description)),
                styles["BodyText"]
            ),
            Paragraph(
                escape(str(transaction.category)),
                styles["BodyText"]
            ),
            transaction.type.title(),
            f"Rs. {transaction.amount:,.2f}"
        ])

    if not transactions:

        transaction_data.append([
            "-",
            "No transactions",
            "-",
            "-",
            "Rs. 0.00"
        ])

    transaction_table = Table(
        transaction_data,
        repeatRows=1,
        colWidths=[
            0.85 * inch,
            1.45 * inch,
            1.05 * inch,
            0.75 * inch,
            1.35 * inch
        ]
    )

    transaction_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#172554")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP")
    ]))

    elements.append(transaction_table)

    # Generate PDF
    document.build(elements)

    pdf_buffer.seek(0)

    filename = (
        f"financial_report_{selected_month}_{selected_year}.pdf"
    )

    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf"
    )


# STEP 21: Create database tables
with app.app_context():

    db.create_all()

    print("MySQL database tables created successfully!")


# STEP 22: Run application
if __name__ == "__main__":
    app.run(
        debug=os.getenv("FLASK_DEBUG", "0") == "1"
    )
