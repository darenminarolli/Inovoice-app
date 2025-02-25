import base64
import os
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash
import pandas as pd
from weasyprint import HTML
from datetime import datetime
import calendar
import random
import string

app = Flask(__name__)
app.secret_key = 'your_secret_key'  


desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", "Invoices")
os.makedirs(desktop_path, exist_ok=True)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = desktop_path

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def get_dates():
    now = datetime.now()
    
    # Determine which month to target: current if day > 3, else previous month.
    if now.day > 3:
        target_year = now.year
        target_month = now.month
    else:
        if now.month == 1:
            target_year = now.year - 1
            target_month = 12
        else:
            target_year = now.year
            target_month = now.month - 1

    # Get the last day of the target month.
    last_day = calendar.monthrange(target_year, target_month)[1]
    last_date = datetime(target_year, target_month, last_day)
    
    # 1. Last day in mm-dd-yy format.
    formatted_last_day = last_date.strftime("%m-%d-%y")
    
    # 2. Month in "Month YYYY" format.
    month_year_format = last_date.strftime("%B %Y")
    
    # 3. Last day formatted as '%y%m' (e.g., 2502 for February 2025).
    last_day_ym = last_date.strftime("%y%m")
    
    return formatted_last_day, month_year_format, last_day_ym
def get_customer_short(name):
    """Extract short symbol for customer based on name."""
    if "AudienceView" in name:
        return "AV"
    start= ''.join(random.choice(string.ascii_uppercase) for x in range(2))
    end= random.choice(string.ascii_uppercase)
    short= name[:2].upper()
    date1, date2, date3 = get_dates()
    invoice = f"{start}-{short}{date3}-{end}"

    return invoice

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file:
            file_path = os.path.join(UPLOAD_FOLDER, file.filename)
            file.save(file_path)
            try:
                generated_files = process_excel(file_path)
                return render_template('results.html', files=generated_files)
            except Exception as e:
                flash(f"Error processing file: {str(e)}")
                return redirect(url_for('index'))
    return render_template('index.html')

def process_excel(file_path):
    """Processes the uploaded Excel file and generates invoices."""
    # Read the Excel file from the "Project Allocation" sheet
    df = pd.read_excel(file_path, sheet_name="Project Allocation", header=0)
    
    # Remove the header row that is part of the data (if any)
    df = df[df['Unnamed: 0'] != 'Customer Name']
    
    # Fill forward the customer name
    df['Customer Name'] = df['Unnamed: 0'].ffill()

    
    projects = df.groupby('Customer Name')
    generated_files = []
    invoice_count = 1
    for customer, group in projects:
        project_info = group.iloc[0]
        project_id = project_info.get('Unnamed: 1', f"INV-{invoice_count:03d}")
        project_start_date = project_info.get('Unnamed: 5')
        project_end_date = project_info.get('Unnamed: 6')

        
        staff_list = []
        for _, row in group.iterrows():
            role = row.get('Unnamed: 2')
            name = row.get('Unnamed: 3')
            company_start_date = row.get('Unnamed: 4')
            if pd.isnull(role) or pd.isnull(name):
                continue
            if pd.notnull(company_start_date):
                try:
                    company_start_date = pd.to_datetime(company_start_date).strftime("%Y-%m-%d")
                except Exception:
                    company_start_date = str(company_start_date)
            staff_list.append({
                'role': role,
                'name': name,
                'start_date': company_start_date
            })
        
        date1, date2, date3 = get_dates()
        current_delivery_period = date2
        invoice_no = get_customer_short(customer)
        billing_date = date1

        
        invoice_data = {
            'company_name': "Ritech International AG",
            'company_details': {
                'address': "DAMMSTRASSE 19, 6300 ZUG, SWITZERLAND",
                'tel': "+41 41 560 734",
                'tax_number': "CHE-281.951.271 MWST"
            },
            'billing_statement': "Billing Statement",
            'billing_date': billing_date,
            'customer_name': customer,
            'customer_address': "Customer address goes here",  # Update if available
            'project_id': project_id,
            'project_start_date': pd.to_datetime(project_start_date).strftime("%Y-%m-%d") if pd.notnull(project_start_date) else "",
            'project_end_date': pd.to_datetime(project_end_date).strftime("%Y-%m-%d") if pd.notnull(project_end_date) else "",
            'invoice_no': invoice_no,
            'item_description': f"Monthly Project Billing for {pd.to_datetime(project_start_date).strftime('%B %Y') if pd.notnull(project_start_date) else ''}",
            'adjustments': "0.00",
            'subtotal': "0.00",
            'vat': "EXEMPT",
            'total': "0.00",
            'staff_list': staff_list,
            'bank_details': {
                'bank_name': "POSTFINANCE AG",
                'bank_address': "3030 BERN, SWITZERLAND",
                'swift': "POFICHBEXXX",
                'account_no': "16-419569-7",
                'iban': "CH72 0900 0000 1641 9569 7"
            },
            'acct_manager': "John Yuzdepski",
            'acct_manager_phone': "+1 (650) 533 2295",
            'delivery_terms': "Net 30 Days",
            'current_delivery_period': current_delivery_period,
            # 'customer_short': customer_short
        }
        with open("static/images/logo-ritech.png", "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        rendered_html = render_template('invoice_template.html', invoice=invoice_data,logo=encoded_image)
        
        safe_customer_name = "".join(c for c in customer if c.isalnum() or c in (' ', '-', '_')).strip()
        output_pdf = os.path.join(OUTPUT_FOLDER, f"{safe_customer_name}.pdf")
        
        # Generate PDF using WeasyPrint
        HTML(string=rendered_html).write_pdf(output_pdf)
        
        generated_files.append(f"{safe_customer_name}.pdf")
        invoice_count += 1
        
    return generated_files

@app.route('/output/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)
 

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Use the PORT environment variable, defaulting to 5000
    app.run(host='0.0.0.0', port=port, debug=True)

