from flask import Blueprint, render_template

from . import db

calculator_bp = Blueprint("calculator", __name__)


@calculator_bp.route("/calculator")
def calculator_view():
    return render_template("calculator.html")
