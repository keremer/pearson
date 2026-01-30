"""
Flask-WTF forms for the web interface.
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, TextAreaField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, Optional

class CourseForm(FlaskForm):
    title = StringField('Course Title', validators=[DataRequired(), Length(max=200)])
    course_code = StringField('Course Code', validators=[DataRequired(), Length(max=50)])
    instructor = StringField('Instructor', validators=[Optional(), Length(max=100)])
    contact_email = StringField('Contact Email', validators=[Optional(), Email(), Length(max=100)])
    level = SelectField('Level', choices=[
        ('', 'Select Level'),
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced')
    ], validators=[Optional()])
    delivery_mode = SelectField('Delivery Mode', choices=[
        ('', 'Select Mode'),
        ('Online', 'Online'),
        ('In-person', 'In-person'),
        ('Hybrid', 'Hybrid')
    ], validators=[Optional()])
    aim = TextAreaField('Course Aim', validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional()])
    objectives = TextAreaField('Learning Objectives', validators=[Optional()])
    submit = SubmitField('Save Course')

class LessonForm(FlaskForm):
    title = StringField('Lesson Title', validators=[DataRequired(), Length(max=200)])
    content = TextAreaField('Content', validators=[Optional()])
    duration = IntegerField('Duration (minutes)', validators=[Optional()], default=60)
    order = IntegerField('Order', validators=[Optional()], default=1)
    activity_type = StringField('Activity Type', validators=[Optional(), Length(max=100)])
    assignment_description = TextAreaField('Assignment Description', validators=[Optional()])
    materials_needed = TextAreaField('Materials Needed', validators=[Optional()])
    submit = SubmitField('Save Lesson')

class ImportForm(FlaskForm):
    file = FileField('Markdown File', validators=[
        FileRequired(),
        FileAllowed(['md'], 'Markdown files only!')
    ])
    submit = SubmitField('Import')