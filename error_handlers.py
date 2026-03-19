from flask import render_template
import logging

logger = logging.getLogger(__name__)

def register_error_handlers(app):

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('404.html', title="404"), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return render_template('500.html', title="500"), 500