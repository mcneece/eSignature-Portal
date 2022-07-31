from app import app

from flask import render_template

@app.route("/admin")
def index():
    "This webpage is for running the Adobe Acrobat Sign Access Check for Users"
    return render_template("admin/admin_dashboard.html")