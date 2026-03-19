from flask import Blueprint, render_template
import logging
import os

# Create a blueprint for static pages
static_pages = Blueprint("static_pages", __name__)

# Setup logging
logger = logging.getLogger(__name__)

# Map of route -> page title
PAGES = {
    "success": "PolicyEdge subscription successful",
    "cancel": "Cancel PolicyEdge subscription",
    "noSubscription": "PolicyEdge subscription not active",
    "about": "About Policy Edge creator Sergio Preciado",
    "termsofservice": "Terms of Service",
    "privacypolicy": "Privacy Policy",
}

def create_static_route(route, title):
    """
    Factory function to generate a unique route for each static page
    """
    endpoint_name = f"static_{route}"  # unique endpoint per route

    @static_pages.route(f"/{route}", endpoint=endpoint_name)
    def _route():
        template_path = f"{route}.html"
        # Check if template exists
        if not os.path.exists(os.path.join("templates", template_path)):
            logger.warning(f"Template not found: {template_path}")
            return f"{route} page not found", 404
        logger.info(f"Serving static page: {route}")
        return render_template(template_path, title=title)

    return _route

# Generate all static page routes dynamically
for route, title in PAGES.items():
    create_static_route(route, title)