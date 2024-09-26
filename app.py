import firebase_admin
from firebase_admin import credentials, storage
import os
from flask import Flask, request, redirect, render_template
from uuid import uuid4
from dotenv import load_dotenv
import mysql.connector

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize Firebase Admin SDK with service account
cred = credentials.Certificate(os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH'))
firebase_admin.initialize_app(cred, {
    'storageBucket': 'python-project-23bb7.appspot.com'  # Use your Firebase bucket name without 'gs://'
})

# Initialize Firebase Storage bucket
bucket = storage.bucket()

# Initialize MySQL database connection
db_connection = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    port=os.getenv('DB_PORT')
)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    phone = request.form['phone']
    email = request.form['email']
    tickets = request.form['tickets']

    # Handle file upload (payment proof)
    payment_proof = request.files['paymentProof']
    
    if not payment_proof:
        return 'No payment proof uploaded.', 400

    # Generate a unique filename for the uploaded file
    payment_proof_filename = f"payments/{uuid4()}_{payment_proof.filename}"
    
    # Upload the file to Firebase Storage
    blob = bucket.blob(payment_proof_filename)
    
    try:
        # Upload the file to Firebase Storage
        blob.upload_from_file(payment_proof, content_type=payment_proof.content_type)
        
         # Make the blob publicly accessible
        blob.make_public()
        
        # Get the public URL for the uploaded file
        payment_proof_url = blob.public_url

        # Create a cursor to interact with the database
        cursor = db_connection.cursor()
        
        # Retrieve the last ticket ID to generate the next one
        cursor.execute("SELECT MAX(ticketId) AS lastTicketId FROM registrations")
        last_ticket_id = cursor.fetchone()[0]
        last_ticket_number = int(last_ticket_id[6:]) if last_ticket_id else 0
        next_ticket_id = f"EVENTID{str(last_ticket_number + 1).zfill(4)}"

        # Insert the registration data into the MySQL database
        cursor.execute("""
            INSERT INTO registrations (name, phone, email, tickets, paymentProofUrl, ticketId)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, phone, email, tickets, payment_proof_url, next_ticket_id))
        
        # Commit the transaction to the database
        db_connection.commit()

        # Redirect to the successful page with the ticket ID
        return redirect(f'/successful.html?ticketId={next_ticket_id}')
    
    except Exception as e:
        print(f'Error during registration: {e}')
        return 'Error processing registration.', 500

@app.route('/successful.html')
def successful():
    ticket_id = request.args.get('ticketId')
    return render_template('successful.html', ticketId=ticket_id)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
