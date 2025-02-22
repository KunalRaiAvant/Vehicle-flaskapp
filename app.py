# app.py
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify,session  
from supabase import create_client, Client
from functools import wraps
from datetime import datetime
import base64
import uuid
import os
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY') # Change this to a secure secret key

# Supabase configuration
supabase: Client = create_client(
    'https://sbzejrhepdceuyvyvsmy.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InNiemVqcmhlcGRjZXV5dnl2c215Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzkyMDk5NjAsImV4cCI6MjA1NDc4NTk2MH0.2YaMv5DUYPIUxOEZ8WnoUwepNJAtqvt6i_2AgD34fr8'
)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    return redirect(url_for('login'))
@app.route('/logout')
def logout():
    session.clear()  # Clear the session data
    return redirect(url_for('login'))
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            session['user_id'] = response.user.id
            session['access_token'] = response.session.access_token
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash('Invalid credentials')
            print(e)
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Registration failed')
            return render_template('register.html')
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    vehicles = supabase.table('vehicles').select("*").eq('user_id', session['user_id']).execute()
    return render_template('dashboard.html', vehicles=vehicles.data)

@app.route('/vehicle/add', methods=['GET', 'POST'])
@login_required
def add_vehicle():
    if request.method == 'POST':
        try:
            # Get the photo data from the form
            photo_data = request.form.get('photo_data')
            photo_url = None

            if photo_data:
                # Remove the data:image/jpeg;base64, prefix
                image_data = photo_data.split(',')[1]
                
                # Decode base64 string to bytes
                image_bytes = base64.b64decode(image_data)
                
                # Generate a unique filename
                filename = f"vehicle_doc_{uuid.uuid4()}.jpg"
                file_options = {
                    "content-type": "image/jpeg"
                }
                
                # Upload to Supabase Storage
                storage_response = supabase.storage \
                    .from_('vehicle-documents') \
                    .upload(filename, image_bytes, file_options)
                
                
                # Get the public URL
                photo_url = supabase.storage \
                    .from_('vehicle-documents') \
                    .get_public_url(filename)

            # Create vehicle data
            vehicle_data = {
                'user_id': session['user_id'],
                'make': request.form['make'],
                'model': request.form['model'],
                'year': request.form['year'],
                'plate_number': request.form['plateNumber'],
                'color': request.form['color'],
                'document_photo': photo_url,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Insert into database
            supabase.table('vehicles').insert(vehicle_data).execute()
            flash('Vehicle added successfully!')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            print(f"Error adding vehicle: {str(e)}")
            flash('Failed to add vehicle')
            return render_template('add_vehicle.html')
    
    return render_template('add_vehicle.html')

@app.route('/vehicle/edit/<uuid:id>', methods=['GET', 'POST'])
@login_required
def edit_vehicle(id):
    if request.method == 'POST':
        photo_data = request.form.get('photo_data')
        photo_url = None
        print(f"Photo data: {photo_data}")


        if photo_data:
            # Remove the data:image/jpeg;base64, prefix
            image_data = photo_data.split(',')[1]
            
            # Decode base64 string to bytes
            image_bytes = base64.b64decode(image_data)
            
            # Generate a unique filename
            filename = f"vehicle_doc_{uuid.uuid4()}.jpg"
            file_options = {
                     "content-type": "image/jpeg"
                }
            
            # Upload to Supabase Storage
            storage_response = supabase.storage \
                .from_('vehicle-documents') \
                .upload(filename, image_bytes)
            
            # Get the public URL
            photo_url = supabase.storage \
                .from_('vehicle-documents') \
                .get_public_url(filename)

        vehicle_data = {
            'user_id': session['user_id'],
            'make': request.form['make'],
            'model': request.form['model'],
            'year': request.form['year'],
            'plate_number': request.form['plateNumber'],
            'color': request.form['color'],
            'document_photo': photo_url,
            'created_at': datetime.utcnow().isoformat()
        }
        
        try:
            supabase.table('vehicles').update(vehicle_data).eq('id', str(id)).execute()
            flash('Vehicle updated successfully!')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash('Failed to update vehicle')
            
    vehicle = supabase.table('vehicles').select("*").eq('id', str(id)).execute()
    print(vehicle)
    return render_template('edit_vehicle.html', vehicle=vehicle.data[0])

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        
        # Check if user is admin
        try:
            user_profile = supabase.table('user_profiles').select('is_admin').eq('id', session['user_id']).execute()
            if not user_profile.data or not user_profile.data[0]['is_admin']:
                flash('Admin access required')
                return redirect(url_for('dashboard'))
        except Exception as e:
            print(f"Error checking admin status: {str(e)}")
            return redirect(url_for('dashboard'))
            
        return f(*args, **kwargs)
    return decorated_function

@app.route('/bookings')
@login_required
def bookings():
    try:
        user_bookings = supabase.table('bookings')\
            .select('*, vehicles(*)').eq('user_id', session['user_id']).execute()
        return render_template('bookings.html', bookings=user_bookings.data)
    except Exception as e:
        flash('Failed to load bookings')
        print(f"Error loading bookings: {str(e)}")
        return render_template('bookings.html', bookings=[])

@app.route('/bookings/new', methods=['GET', 'POST'])
@login_required
def new_booking():
    if request.method == 'POST':
        try:
            booking_data = {
                'user_id': session['user_id'],
                'source': request.form['source'],
                'destination': request.form['destination'],
                'booking_date': request.form['date'],
                'created_at': datetime.utcnow().isoformat()
            }
            supabase.postgrest.auth(session.get('access_token'))
            result = supabase.table('bookings').insert(booking_data).execute()
            if result.data:
                flash('Booking submitted successfully!')
                return redirect(url_for('bookings'))
            else:
                flash('Failed to create booking')
                return render_template('booking_form.html')
            return redirect(url_for('bookings'))
        except Exception as e:
            flash('Failed to create booking')
            print(f"Error creating booking: {str(e)}")
            
    return render_template('new_booking.html')

@app.route('/admin/bookings')
@login_required
@admin_required
def admin_bookings():
    try:
        all_bookings = supabase.table('bookings')\
            .select('*, vehicles(*), auth.users!bookings_user_id_fkey(email)')\
            .execute()
        return render_template('admin_bookings.html', bookings=all_bookings.data)
    except Exception as e:
        flash('Failed to load bookings')
        print(f"Error loading admin bookings: {str(e)}")
        return render_template('admin_bookings.html', bookings=[])


@app.route('/admin/bookings/<uuid:id>', methods=['POST'])
@login_required
@admin_required
def update_booking(id):
    try:
        data = request.form
        update_data = {
            'status': data.get('status'),
            'amount': float(data.get('amount', 0)) if data.get('amount') else None,
            'vehicle_id': data.get('vehicle_id')
        }
        
        supabase.table('bookings').update(update_data).eq('id', str(id)).execute()
        flash('Booking updated successfully!')
    except Exception as e:
        flash('Failed to update booking')
        print(f"Error updating booking: {str(e)}")
        
    return redirect(url_for('admin_bookings'))

@app.route('/bookings/<uuid:id>/pay', methods=['POST'])
@login_required
def pay_booking(id):
    try:
        # Here you would integrate with your payment provider
        # For now, we'll just mark it as paid
        supabase.table('bookings')\
            .update({'status': 'paid'})\
            .eq('id', str(id))\
            .eq('user_id', session['user_id'])\
            .execute()
        flash('Payment processed successfully!')
    except Exception as e:
        flash('Payment processing failed')
        print(f"Error processing payment: {str(e)}")
        
    return redirect(url_for('bookings'))


@app.route('/vehicle/delete/<uuid:id>')
@login_required
def delete_vehicle(id):
    try:
        supabase.table('vehicles').delete().eq('id', str(id)).execute()
        flash('Vehicle deleted successfully!')
    except Exception as e:
        flash('Failed to delete vehicle')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)