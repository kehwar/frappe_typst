app_name = "frappe_typst"
app_title = "Frappe Typst"
app_publisher = "@kehwar"
app_description = "Typst integration"
app_email = "erickkwr@gmail.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["kehwar/frappe"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "frappe_typst",
# 		"logo": "/assets/frappe_typst/logo.png",
# 		"title": "Frappe Typst",
# 		"route": "/frappe_typst",
# 		"has_permission": "frappe_typst.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/frappe_typst/css/frappe_typst.css"
# app_include_js = "/assets/frappe_typst/js/frappe_typst.js"

# include js, css files in header of web template
# web_include_css = "/assets/frappe_typst/css/frappe_typst.css"
# web_include_js = "/assets/frappe_typst/js/frappe_typst.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "frappe_typst/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "frappe_typst/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "frappe_typst.utils.jinja_methods",
# 	"filters": "frappe_typst.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "frappe_typst.install.before_install"
# after_install = "frappe_typst.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "frappe_typst.uninstall.before_uninstall"
# after_uninstall = "frappe_typst.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "frappe_typst.utils.before_app_install"
# after_app_install = "frappe_typst.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "frappe_typst.utils.before_app_uninstall"
# after_app_uninstall = "frappe_typst.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "frappe_typst.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"frappe_typst.tasks.all"
# 	],
# 	"daily": [
# 		"frappe_typst.tasks.daily"
# 	],
# 	"hourly": [
# 		"frappe_typst.tasks.hourly"
# 	],
# 	"weekly": [
# 		"frappe_typst.tasks.weekly"
# 	],
# 	"monthly": [
# 		"frappe_typst.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "frappe_typst.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "frappe_typst.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "frappe_typst.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["frappe_typst.utils.before_request"]
# after_request = ["frappe_typst.utils.after_request"]

# Job Events
# ----------
# before_job = ["frappe_typst.utils.before_job"]
# after_job = ["frappe_typst.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"frappe_typst.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# ---------------------------------------------------------------------------
# Typst hooks
# ---------------------------------------------------------------------------

after_install = ["frappe_typst.utils.setup.install"]
before_uninstall = ["frappe_typst.utils.setup.uninstall"]

get_print_format_template = [
    "frappe_typst.utils.print_format.get_print_format_template"
]
pdf_generator = ["frappe_typst.utils.print_format.pdf_generator"]

page_js = {"print": "public/js/print_typst_view.js"}
doctype_js = {"Print Format": "public/js/print_format_typst.js"}

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
