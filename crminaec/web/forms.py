"""
Flask-WTF forms for the web interface.
Merged: Enhanced UX + Data-First Architecture Compatibility
"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (IntegerField, SelectField, StringField, SubmitField,
                     TextAreaField)
from wtforms.validators import DataRequired, Email, Length, Optional


class CourseForm(FlaskForm):
    """Form for creating and editing Courses"""
    title = StringField('Course Title', validators=[DataRequired(), Length(max=200)])
    course_code = StringField('Course Code', validators=[DataRequired(), Length(max=50)])
    
    instructor = StringField('Instructor', validators=[Optional(), Length(max=100)])
    contact_email = StringField('Contact Email', validators=[Optional(), Email(), Length(max=100)])
    
    level = SelectField('Level', choices=[
        ('', 'Select Level'),
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
        ('HND Art & Design', 'HND Art & Design') # Added based on your syllabus injector!
    ], validators=[Optional()])
    
    # NEW: Added language to satisfy the Dataclass model and Pylance
    language = StringField('Language', default='English', validators=[Optional(), Length(max=50)])
    
    delivery_mode = SelectField('Delivery Mode', choices=[
        ('', 'Select Mode'),
        ('Online', 'Online'),
        ('In-person', 'In-person'),
        ('Hybrid', 'Hybrid'),
        ('Blended', 'Blended') # Added based on your syllabus injector!
    ], validators=[Optional()])
    
    aim = TextAreaField('Course Aim', validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional()])
    objectives = TextAreaField('Learning Objectives', validators=[Optional()])
    
    submit = SubmitField('Save Course')


class LessonForm(FlaskForm):
    """Form for creating and editing Lessons"""
    title = StringField('Lesson Title', validators=[DataRequired(), Length(max=200)])
    order = IntegerField('Week/Order', validators=[Optional()], default=1)
    duration = IntegerField('Duration (minutes)', validators=[Optional()], default=60)
    
    activity_type = StringField('Activity Type', validators=[Optional(), Length(max=100)])
    content = TextAreaField('Content', validators=[Optional()])
    assignment_description = TextAreaField('Assignment Description', validators=[Optional()])
    materials_needed = TextAreaField('Materials Needed', validators=[Optional()])
    
    submit = SubmitField('Save Lesson')


class ImportForm(FlaskForm):
    """Form for uploading Markdown syllabi"""
    file = FileField('Markdown File', validators=[
        FileRequired(),
        FileAllowed(['md'], 'Markdown files only!')
    ])
    submit = SubmitField('Import')