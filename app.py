from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import pymysql
import json
import bcrypt  
import uuid  
import secrets  
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__)

# Database setup
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'kubastoklosa'
app.config['MYSQL_DB'] = 'knowledge_mapping'

# Flask-Login setup
app.secret_key = secrets.token_hex(16) 
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Database connection function to avoid repetition
def get_db_connection():
    conn = pymysql.connect(
        host=app.config['MYSQL_HOST'],
        user=app.config['MYSQL_USER'],
        password=app.config['MYSQL_PASSWORD'],
        database=app.config['MYSQL_DB']
    )
    return conn

# Load user from the database
@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if user:
        return User(user[0])
    return None

# Routes
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        # Check if user exists and password is correct
        if user and bcrypt.checkpw(password.encode('utf-8'), user[2].encode('utf-8')):  # index 2 for password_hash
            user_obj = User(user[0])  # user[0] is the user id
            login_user(user_obj)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        
        # Hash the password before storing it
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12))
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Insert the username and hashed password into the database
            cur.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", 
                        (username, hashed_password))
            conn.commit()
            flash("Your account has been successfully created! You can now log in.", "success")  # Flash success message
            return redirect(url_for("login"))
        except pymysql.err.IntegrityError as e:
            flash("Username already exists", "danger")
        finally:
            cur.close()
            conn.close()
    return render_template("register.html")

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.map_id, m.title, u.username
        FROM shared_maps sm
        JOIN maps m ON sm.map_id = m.map_id
        JOIN users u ON m.user_id = u.id
        WHERE sm.shared_with_id = %s
        ORDER BY sm.shared_at DESC
        LIMIT 3
    """, (current_user.id,))
    
    shared_maps = []
    for row in cur.fetchall():
        shared_maps.append({
            "map_id": row[0],
            "title": row[1],
            "username": row[2]
        })
    
    cur.close()
    conn.close()
    
    return render_template("dashboard.html", shared_maps=shared_maps)

@app.route("/view_personal_maps")
@login_required
def view_personal_maps():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.map_id, m.title, m.description, 
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as rating_count
        FROM maps m
        LEFT JOIN ratings r ON m.map_id = r.map_id
        WHERE m.user_id = %s
        GROUP BY m.map_id, m.title, m.description
    """, (current_user.id,))
    
    maps = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("view_maps.html", maps=maps)

@app.route('/map_editor/<map_id>', methods=['GET', 'POST'])
@login_required
def map_editor(map_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # Check if the map exists and get its basic information including the author ID
    cur.execute("SELECT m.title, m.description, m.user_id FROM maps m WHERE map_id = %s", (map_id,))
    map_data = cur.fetchone()
    
    if not map_data:
        flash("Map not found", "danger")
        return redirect(url_for('view_personal_maps'))
    
    # Store map details
    map_title = map_data[0]
    map_description = map_data[1]
    author_id = map_data[2]
    
    # Get the author's username
    cur.execute("SELECT username FROM users WHERE id = %s", (author_id,))
    author_name = cur.fetchone()[0]

    # Always add current user as editor when visiting the page (except if they're the author)
    if current_user.id != author_id:
        # Check if the user is already an editor
        cur.execute("SELECT 1 FROM editors WHERE map_id = %s AND user_id = %s", (map_id, current_user.id))
        is_editor = cur.fetchone()
        
        if not is_editor:
            try:
                cur.execute("INSERT INTO editors (map_id, user_id) VALUES (%s, %s)", (map_id, current_user.id))
                conn.commit()
                print(f"Added user {current_user.id} as editor for map {map_id}")
            except Exception as e:
                print(f"Error adding editor: {e}")
                conn.rollback()

    # Fetch the names of all editors who have edited the map
    cur.execute("""
        SELECT DISTINCT u.username FROM editors e
        JOIN users u ON e.user_id = u.id
        WHERE e.map_id = %s
    """, (map_id,))
    editors_data = [row[0] for row in cur.fetchall()]
    
    print(f"Editors for map {map_id}: {editors_data}")

    cur.execute("SELECT id, label, description, position_x, position_y, shape, color, size FROM nodes WHERE map_id = %s", (map_id,))
    nodes_data = []
    for row in cur.fetchall():
        size = row[7]
        try:
            size = json.loads(size)  # Parse dict like {"width": 50, "height": 50}
        except (TypeError, json.JSONDecodeError):
            size = int(size) if size else 35  # Fallback for plain numbers or None

        nodes_data.append({
            "id": row[0],
            "label": row[1],
            "description": row[2],
            "x": row[3],
            "y": row[4],
            "shape": row[5] if row[5] else "circle",
            "color": row[6] if row[6] else "steelblue",
            "size": size
        })


    # Fetch links as dictionaries
    cur.execute("""
        SELECT l.id, s.label AS source_label, t.label AS target_label, l.type, l.distance
        FROM links l
        JOIN nodes s ON l.source_node_id = s.id
        JOIN nodes t ON l.target_node_id = t.id
        WHERE l.map_id = %s
    """, (map_id,))



    links_data = [{
        "id": row[0],
        "sourceLabel": row[1],
        "targetLabel": row[2],
        "type": row[3] if row[3] else "line",
        "distance": row[4] if row[4] else 100
    } for row in cur.fetchall()]

    # Get average rating and count
    cur.execute("SELECT AVG(rating), COUNT(*) FROM ratings WHERE map_id = %s", (map_id,))
    avg_rating_row = cur.fetchone()
    average_rating = round(avg_rating_row[0], 2) if avg_rating_row[0] else 0
    rating_count = avg_rating_row[1]

    # Get list of raters and their ratings
    cur.execute("""
        SELECT u.username, r.rating
        FROM ratings r
        JOIN users u ON r.user_id = u.id
        WHERE r.map_id = %s
    """, (map_id,))
    raters = cur.fetchall()
    raters_data = [{"username": r[0], "rating": r[1]} for r in raters]



    cur.close()
    conn.close()

    # Pass the map title, nodes, links, author name and editors to the template
    return render_template(
        "edit_map.html",
        map_id=map_id,
        map_title=map_title,
        nodes_data=nodes_data if nodes_data else [],
        links_data=links_data if links_data else [],
        editors_data=editors_data,
        author_name=author_name,
        average_rating=average_rating,
        rating_count=rating_count,
        raters_data=raters_data
    )



@app.route('/delete_map', methods=['POST'])
def delete_map():
    data = request.json
    map_id = data.get('mapId')

    if not map_id:
        return jsonify({'error': 'Map ID is required'}), 400

    conn = get_db_connection()  # Create a connection using your get_db_connection function
    cur = conn.cursor()

    # Execute the deletion query
    cur.execute("DELETE FROM maps WHERE map_id = %s", (map_id,))

    # Commit the changes
    conn.commit()

    # Close the cursor and connection
    cur.close()
    conn.close()

    return jsonify({'message': 'Map deleted successfully'})




# Create a new knowledge map with UUID
@app.route("/create_knowledge_map", methods=["GET", "POST"])
@login_required
def create_knowledge_map():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        map_id = str(uuid.uuid4())  # Generate a unique ID

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("INSERT INTO maps (map_id, user_id, title, description) VALUES (%s, %s, %s, %s)",
                    (map_id, current_user.id, title, description))
        conn.commit()
        cur.close()
        conn.close()
        
        flash(f"Your new knowledge map has been created! You can now start building your map.", "success")
        return redirect(url_for("edit_knowledge_map", map_id=map_id))

    return render_template("create_map.html")

# Edit/Start building a new knowledge map (blank canvas)
@app.route("/edit_knowledge_map/<map_id>", methods=["GET", "POST"])
@login_required
def edit_knowledge_map(map_id):
    # Get the map details
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM maps WHERE map_id = %s", (map_id,))
    map_data = cur.fetchone()
    
    if not map_data or map_data[1] != current_user.id:  # Check if the map exists and belongs to the current user
        flash("This map does not belong to you or doesn't exist.", "danger")
        return redirect(url_for("view_personal_maps"))

    # Define nodes_data and links_data before using them
    nodes_data = []
    links_data = []

    # Fetch nodes and links related to this map
    cur.execute("SELECT * FROM nodes WHERE map_id = %s", (map_id,))
    nodes_data = cur.fetchall()

    cur.execute("SELECT * FROM links WHERE map_id = %s", (map_id,))
    links_data = cur.fetchall()

    cur.close()
    conn.close()

    print(f"nodes_data: {nodes_data}")
    print(f"links_data: {links_data}")

    return render_template("edit_map.html", map_id=map_id, nodes_data=nodes_data, links_data=links_data)


# View other members' knowledge maps
@app.route("/view_other_maps")
@login_required
def view_other_maps():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("""
        SELECT m.map_id, m.title, m.description, 
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as rating_count
        FROM maps m
        LEFT JOIN ratings r ON m.map_id = r.map_id
        WHERE m.user_id != %s
        GROUP BY m.map_id, m.title, m.description
    """, (current_user.id,))
    
    maps = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("view_maps.html", maps=maps)

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))

@app.route("/enter_map_id", methods=["GET", "POST"])
@login_required
def enter_map_id():
    if request.method == "POST":
        map_id = request.form["map_id"].strip()  # Get the entered Map ID

        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if the map ID exists in the database
        cur.execute("SELECT user_id FROM maps WHERE map_id = %s", (map_id,))
        result = cur.fetchone()
        
        cur.close()
        conn.close()

        if result:
            # If the map exists, check if the user is authorized to view/edit it
            user_id_of_map = result[0]
            if user_id_of_map == current_user.id:  # If it's the user's own map
                return redirect(url_for("map_editor", map_id=map_id))
            else:
                # Optionally, add an additional check to verify the user can edit this map.
                # For example, if the map is public or the user has permission.
                # For now, let's assume that any map is accessible if the ID is valid.
                return redirect(url_for("map_editor", map_id=map_id))
        else:
            flash("Invalid Map ID. Please try again.", "danger")
            return redirect(url_for("enter_map_id"))

    return render_template("enter_map_id.html")

@app.route("/save_map", methods=["POST"])
@login_required
def save_map():
    map_data = request.json
    map_id = map_data['mapId']
    nodes = map_data['nodes']
    links = map_data['links']

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Delete links first
        cur.execute("""
            DELETE l FROM links l
            JOIN nodes s ON l.source_node_id = s.id
            JOIN nodes t ON l.target_node_id = t.id
            WHERE s.map_id = %s OR t.map_id = %s
        """, (map_id, map_id))

        # Delete nodes
        cur.execute("DELETE FROM nodes WHERE map_id = %s", (map_id,))

        # Track new node IDs
        node_ids = {}
        for node in nodes:
            size = node.get("size")
            size_str = json.dumps(size) if isinstance(size, dict) else str(size)

            cur.execute(
                "INSERT INTO nodes (map_id, label, description, position_x, position_y, shape, color, size) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    map_id,
                    node['label'],
                    node.get('description', ''),
                    node['x'],
                    node['y'],
                    node.get('shape', 'circle'),
                    node.get('color', 'steelblue'),
                    size_str
                )
            )
            node_ids[node['label']] = cur.lastrowid

        for link in links:
            source_id = node_ids.get(link['sourceLabel'])
            target_id = node_ids.get(link['targetLabel'])
            link_type = link.get("type", "line")
            distance = link.get("distance", 100)

            if source_id and target_id:
                cur.execute(
                    "INSERT INTO links (map_id, source_node_id, target_node_id, type, distance) VALUES (%s, %s, %s, %s, %s)",
                    (map_id, source_id, target_id, link_type, distance)
                )

        conn.commit()
        return jsonify({"status": "success"})

    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route("/rate_map", methods=["POST"])
@login_required
def rate_map():
    data = request.json
    map_id = data["mapId"]
    rating = data["rating"]

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO ratings (map_id, user_id, rating)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE rating = VALUES(rating)
        """, (map_id, current_user.id, rating))
        conn.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        conn.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        cur.close()
        conn.close()

@app.route("/share_map/<map_id>", methods=["GET", "POST"])
@login_required
def share_map(map_id):
    # Check if the map belongs to the current user
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get map details
    cur.execute("SELECT title, user_id FROM maps WHERE map_id = %s", (map_id,))
    map_data = cur.fetchone()
    
    if not map_data:
        flash("Map not found", "danger")
        return redirect(url_for('view_personal_maps'))
    
    map_title = map_data[0]
    map_owner_id = map_data[1]
    
    if map_owner_id != current_user.id:
        flash("You can only share maps that you own", "danger")
        return redirect(url_for('map_editor', map_id=map_id))
    
    # Get all users except the current user
    cur.execute("SELECT id, username FROM users WHERE id != %s ORDER BY username", (current_user.id,))
    users = [{"id": row[0], "username": row[1]} for row in cur.fetchall()]
    
    # Get users this map is already shared with
    cur.execute("SELECT shared_with_id FROM shared_maps WHERE map_id = %s", (map_id,))
    shared_with = [row[0] for row in cur.fetchall()]
    
    # Handle form submission
    if request.method == "POST":
        selected_users = request.form.getlist('selected_users')
        
        # Convert to integers
        selected_users = [int(user_id) for user_id in selected_users]
        
        # Delete shares that were unchecked
        users_to_remove = [user_id for user_id in shared_with if user_id not in selected_users]
        if users_to_remove:
            placeholders = ','.join(['%s'] * len(users_to_remove))
            cur.execute(f"DELETE FROM shared_maps WHERE map_id = %s AND shared_with_id IN ({placeholders})", 
                       [map_id] + users_to_remove)
        
        # Add new shares
        users_to_add = [user_id for user_id in selected_users if user_id not in shared_with]
        for user_id in users_to_add:
            try:
                cur.execute("""
                    INSERT INTO shared_maps (map_id, owner_id, shared_with_id) 
                    VALUES (%s, %s, %s)
                """, (map_id, current_user.id, user_id))
            except pymysql.err.IntegrityError:
                # Skip if already exists (shouldn't happen with our logic, but just in case)
                continue
        
        conn.commit()
        flash("Map sharing preferences updated", "success")
        return redirect(url_for('map_editor', map_id=map_id))
    
    cur.close()
    conn.close()
    
    return render_template("share_map.html", map_id=map_id, map_title=map_title, users=users, shared_with=shared_with)

@app.route("/maps_shared_with_me")
@login_required
def maps_shared_with_me():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Get maps shared with the current user, including owner name and ratings
    cur.execute("""
        SELECT m.map_id, m.title, m.description, u.username, 
               ROUND(AVG(r.rating), 1) as avg_rating,
               COUNT(r.id) as rating_count
        FROM shared_maps sm
        JOIN maps m ON sm.map_id = m.map_id
        JOIN users u ON m.user_id = u.id
        LEFT JOIN ratings r ON m.map_id = r.map_id
        WHERE sm.shared_with_id = %s
        GROUP BY m.map_id, m.title, m.description, u.username
        ORDER BY sm.shared_at DESC
    """, (current_user.id,))
    
    shared_maps = []
    for row in cur.fetchall():
        shared_maps.append({
            "map_id": row[0],
            "title": row[1],
            "description": row[2],
            "username": row[3],
            "avg_rating": row[4],
            "rating_count": row[5]
        })
    
    cur.close()
    conn.close()
    
    return render_template("maps_shared_with_me.html", shared_maps=shared_maps)

if __name__ == "__main__":
    app.run(debug=True)