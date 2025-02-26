import base64
import os
from flask import Flask, request, render_template, send_file, redirect, url_for, flash
import pandas as pd
from weasyprint import HTML
from datetime import datetime
import calendar
import random
import string
import io
import zipfile

app = Flask(__name__)
app.secret_key = 'your_secret_key'

def get_dates():
    now = datetime.now()
    # Use current month if day > 3, else previous month
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

    last_day = calendar.monthrange(target_year, target_month)[1]
    last_date = datetime(target_year, target_month, last_day)
    formatted_last_day = last_date.strftime("%m-%d-%y")
    month_year_format = last_date.strftime("%B %Y")
    last_day_ym = last_date.strftime("%y%m")
    return formatted_last_day, month_year_format, last_day_ym

def get_customer_short(name):
    """Generate a short invoice number based on the customer name."""
    if "AudienceView" in name:
        return "AV"
    start = ''.join(random.choice(string.ascii_uppercase) for _ in range(2))
    end = random.choice(string.ascii_uppercase)
    short = name[:2].upper()
    _, _, date3 = get_dates()
    invoice = f"{start}-{short}{date3}-{end}"
    return invoice

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        file = request.files.get('excel_file')
        if file:
            try:
                # Process the Excel file and generate in-memory PDFs
                invoices = process_excel(file)
                
                # Package all PDFs into an in-memory ZIP file
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zip_file:
                    for inv in invoices:
                        zip_file.writestr(inv['filename'], inv['pdf_data'])
                zip_buffer.seek(0)
                
                # Return the ZIP file for download
                return send_file(
                    zip_buffer,
                    as_attachment=True,
                    download_name="invoices.zip",
                    mimetype="application/zip"
                )
            except Exception as e:
                flash(f"Error processing file: {str(e)}")
                return redirect(url_for('index'))
    return render_template('index.html')

def process_excel(file):
    """
    Processes the uploaded Excel file and generates PDFs in memory.
    Returns a list of dictionaries with each invoice's filename and PDF bytes.
    """
    # Read Excel file from the file-like object
    df = pd.read_excel(file, sheet_name="Project Allocation", header=0, engine='openpyxl')
    df = df[df['Unnamed: 0'] != 'Customer Name']
    df['Customer Name'] = df['Unnamed: 0'].ffill()
    
    projects = df.groupby('Customer Name')
    invoices = []
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
            'customer_address': "Customer address goes here",
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
        }

        with open("static/images/logo-ritech.png", "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')

        rendered_html = render_template('invoice_template.html', invoice=invoice_data, logo=encoded_image)
        
        # Generate PDF in memory
        pdf_buffer = io.BytesIO()
        HTML(string=rendered_html).write_pdf(pdf_buffer)
        pdf_buffer.seek(0)
        pdf_data = pdf_buffer.read()
        
        safe_customer_name = "".join(c for c in customer if c.isalnum() or c in (' ', '-', '_')).strip()
        filename = f"{safe_customer_name}.pdf"
        
        invoices.append({'filename': filename, 'pdf_data': pdf_data})
        invoice_count += 1

    return invoices

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
