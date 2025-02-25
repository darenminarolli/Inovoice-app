import os
from flask import Flask, request, render_template, send_from_directory, redirect, url_for, flash
import pandas as pd
import pdfkit
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change to a secure key

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def get_customer_short(name):
    """Extract short symbol for customer based on name."""
    if "AudienceView" in name:
        return "AV"
    return name[:2].upper()

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
    df['Customer Name'] = df['Unnamed: 0'].fillna(method='ffill')
    
    projects = df.groupby('Customer Name')
    generated_files = []
    invoice_count = 1
    for customer, group in projects:
        project_info = group.iloc[0]
        project_id = project_info.get('Unnamed: 1', f"INV-{invoice_count:03d}")
        project_start_date = project_info.get('Unnamed: 5')
        project_end_date = project_info.get('Unnamed: 6')
        billing_date = datetime.now().strftime("%m/%d/%Y")
        
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
        
        current_delivery_period = datetime.now().strftime("%B %Y")
        customer_short = get_customer_short(customer)
        invoice_no = f"AG-{customer_short}{datetime.now().strftime('%y%m')}-A"
        
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
            'customer_short': customer_short
        }
        
        rendered_html = render_template('invoice_template.html', invoice=invoice_data)
        
        # Configure wkhtmltopdf path if needed (adjust the path accordingly)
        path_wkhtmltopdf = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        config = pdfkit.configuration(wkhtmltopdf=path_wkhtmltopdf)
        safe_customer_name = "".join(c for c in customer if c.isalnum() or c in (' ', '-', '_')).strip()
        output_pdf = os.path.join(OUTPUT_FOLDER, f"{safe_customer_name}.pdf")
        pdfkit.from_string(rendered_html, output_pdf, configuration=config)
        generated_files.append(f"invoice_{invoice_count}.pdf")
        invoice_count += 1
        
    return generated_files

@app.route('/output/<filename>')
def download_file(filename):
    # return send_from_directory(OUTPUT_FOLDER, filename)
    return 

if __name__ == '__main__':
    app.run(debug=True)
