// Course Management System JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-resize textareas
    const autoResizeTextareas = document.querySelectorAll('textarea');
    autoResizeTextareas.forEach(textarea => {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });
        
        // Trigger initial resize
        textarea.dispatchEvent(new Event('input'));
    });

    // Confirm before destructive actions
    const confirmForms = document.querySelectorAll('form[onsubmit]');
    confirmForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const confirmMessage = this.getAttribute('onsubmit')?.match(/return confirm\('([^']+)'\)/)?.[1];
            if (confirmMessage && !confirm(confirmMessage)) {
                e.preventDefault();
            }
        });
    });

    // Auto-calculate duration based on activity type
    const activityTypeSelect = document.getElementById('activity_type');
    const durationInput = document.getElementById('duration');
    
    if (activityTypeSelect && durationInput) {
        activityTypeSelect.addEventListener('change', function() {
            const activity = this.value.toLowerCase();
            let duration = 60; // default
            
            if (activity.includes('workshop') || activity.includes('demo') || 
                activity.includes('simulation') || activity.includes('role play')) {
                duration = 120;
            } else if (activity.includes('presentation') || activity.includes('discussion') || 
                       activity.includes('analysis')) {
                duration = 90;
            }
            
            durationInput.value = duration;
        });
    }

    // Flash message auto-dismiss
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Enhanced form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = this.querySelectorAll('[required]');
            let valid = true;
            
            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    valid = false;
                    field.classList.add('is-invalid');
                    
                    // Add error message if not exists
                    if (!field.nextElementSibling?.classList.contains('invalid-feedback')) {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'invalid-feedback';
                        errorDiv.textContent = 'This field is required.';
                        field.parentNode.appendChild(errorDiv);
                    }
                } else {
                    field.classList.remove('is-invalid');
                    field.classList.add('is-valid');
                }
            });
            
            if (!valid) {
                e.preventDefault();
                // Scroll to first error
                const firstError = this.querySelector('.is-invalid');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstError.focus();
                }
            }
        });
    });

    // Remove validation classes on input
    document.addEventListener('input', function(e) {
        if (e.target.hasAttribute('required')) {
            e.target.classList.remove('is-invalid', 'is-valid');
            if (e.target.value.trim()) {
                e.target.classList.add('is-valid');
            }
        }
    });

    // Quick search functionality for courses
    const courseSearch = document.getElementById('courseSearch');
    if (courseSearch) {
        courseSearch.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const courseCards = document.querySelectorAll('.course-card');
            
            courseCards.forEach(card => {
                const title = card.querySelector('.card-title').textContent.toLowerCase();
                const code = card.querySelector('.text-muted').textContent.toLowerCase();
                const description = card.querySelector('.card-text').textContent.toLowerCase();
                
                if (title.includes(searchTerm) || code.includes(searchTerm) || description.includes(searchTerm)) {
                    card.parentElement.style.display = 'block';
                } else {
                    card.parentElement.style.display = 'none';
                }
            });
        });
    }
});

// API functions for future enhancements
const CourseAPI = {
    async getCourses() {
        try {
            const response = await fetch('/api/courses');
            return await response.json();
        } catch (error) {
            console.error('Error fetching courses:', error);
            return [];
        }
    },
    
    async getCourseLessons(courseId) {
        try {
            const response = await fetch(`/api/course/${courseId}/lessons`);
            return await response.json();
        } catch (error) {
            console.error('Error fetching lessons:', error);
            return [];
        }
    }
};

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { CourseAPI };
}