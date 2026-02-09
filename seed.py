import random
from datetime import datetime, timedelta
from app2.database import get_connection

def seed_data():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Clear existing data for a fresh seed
    cursor.execute("DELETE FROM sales")
    cursor.execute("DELETE FROM expenses")
    cursor.execute("DELETE FROM customers")
    
    # Configurations
    categories = ["Alquiler", "Sueldos", "Marketing", "Suministros", "Mantenimiento"]
    regions = ["Norte", "Sur", "Centro"]
    channels = ["Online", "Tienda Física"]
    segments = ["Minorista", "Mayorista", "Corporativo"]
    
    # Generate 6 months of data
    start_date = datetime.now() - timedelta(days=180)
    
    for i in range(180):
        current_date = (start_date + timedelta(days=i)).strftime('%Y-%m-%d')
        month = (start_date + timedelta(days=i)).month
        
        # Sales Logic: General growth, but a drop in Month 5 (May)
        base_sales = 3000
        if month == 5: # Artificial drop
            base_sales = 1500
        elif month == 6: # Recovery
            base_sales = 4500
            
        # Daily sales entries
        for _ in range(random.randint(2, 5)):
            cursor.execute(
                "INSERT INTO sales (date, amount, region, channel) VALUES (?, ?, ?, ?)",
                (current_date, base_sales + random.uniform(-500, 500), random.choice(regions), random.choice(channels))
            )
            
        # Expenses Logic: Monthly fixed + random variables
        if i % 30 == 0: # Monthly fixed costs
            cursor.execute("INSERT INTO expenses (date, category, amount) VALUES (?, ?, ?)", (current_date, "Alquiler", 15000))
            cursor.execute("INSERT INTO expenses (date, category, amount) VALUES (?, ?, ?)", (current_date, "Sueldos", 35000))
            
        # Marketing/Suministros (more frequent)
        if random.random() > 0.7:
            # Anomaly: High maintenance cost in month 6
            amt = random.uniform(200, 800)
            cat = random.choice(categories[2:])
            if month == 6 and cat == "Mantenimiento":
                amt = 5000 # Cost spike
            cursor.execute("INSERT INTO expenses (date, category, amount) VALUES (?, ?, ?)", (current_date, cat, amt))

    # Customers
    for _ in range(150):
        cursor.execute("INSERT INTO customers (segment, active) VALUES (?, ?)", (random.choice(segments), 1))
        
    conn.commit()
    conn.close()
    print("Database seeded successfully with 6 months of data.")
