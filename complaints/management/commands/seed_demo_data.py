import sys
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import Profile
from complaints.models import Category, Complaint, ComplaintHistory


class Command(BaseCommand):
    help = "Seeds database with demo users, standard categories, and realistic sample complaints across all statuses."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Deletes existing demo data before seeding.',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seeding Campus Complaint System Demo Data ==="))

        if options['clear']:
            self.stdout.write(self.style.WARNING("Clearing existing complaints, categories, and demo users..."))
            ComplaintHistory.objects.all().delete()
            Complaint.objects.all().delete()
            Category.objects.all().delete()
            User.objects.filter(username__in=['admin', 'staff1', 'staff2', 'student1', 'student2', 'student3']).delete()

        # -------------------------------------------------------------
        # 1. Create Demo Users
        # -------------------------------------------------------------
        self.stdout.write("--> Creating Demo Users...")
        
        users_data = [
            {
                'username': 'admin',
                'email': 'admin@campus.edu',
                'password': 'admin',
                'first_name': 'Campus',
                'last_name': 'Admin',
                'role': Profile.ROLE_ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'phone': '+91 98765 00000',
            },
            {
                'username': 'staff1',
                'email': 'staff1@campus.edu',
                'password': 'staff1pass',
                'first_name': 'Rajesh',
                'last_name': 'Kumar',
                'role': Profile.ROLE_STAFF,
                'is_staff': True,
                'is_superuser': False,
                'phone': '+91 98765 43210',
            },
            {
                'username': 'staff2',
                'email': 'staff2@campus.edu',
                'password': 'staff2pass',
                'first_name': 'Anita',
                'last_name': 'Sharma',
                'role': Profile.ROLE_STAFF,
                'is_staff': True,
                'is_superuser': False,
                'phone': '+91 98765 43211',
            },
            {
                'username': 'student1',
                'email': 'student1@campus.edu',
                'password': 'student1pass',
                'first_name': 'Aarav',
                'last_name': 'Patel',
                'role': Profile.ROLE_STUDENT,
                'is_staff': False,
                'is_superuser': False,
                'phone': '+91 98765 11111',
            },
            {
                'username': 'student2',
                'email': 'student2@campus.edu',
                'password': 'student2pass',
                'first_name': 'Diya',
                'last_name': 'Menon',
                'role': Profile.ROLE_STUDENT,
                'is_staff': False,
                'is_superuser': False,
                'phone': '+91 98765 22222',
            },
            {
                'username': 'student3',
                'email': 'student3@campus.edu',
                'password': 'student3pass',
                'first_name': 'Rohan',
                'last_name': 'Gupta',
                'role': Profile.ROLE_STUDENT,
                'is_staff': False,
                'is_superuser': False,
                'phone': '+91 98765 33333',
            },
        ]

        created_users = {}
        for udata in users_data:
            user, created = User.objects.get_or_create(
                username=udata['username'],
                defaults={
                    'email': udata['email'],
                    'first_name': udata['first_name'],
                    'last_name': udata['last_name'],
                    'is_staff': udata['is_staff'],
                    'is_superuser': udata['is_superuser'],
                }
            )
            user.set_password(udata['password'])
            user.email = udata['email']
            user.first_name = udata['first_name']
            user.last_name = udata['last_name']
            user.is_staff = udata['is_staff']
            user.is_superuser = udata['is_superuser']
            user.is_active = True
            user.save()

            # Ensure profile has correct role and phone
            profile, _ = Profile.objects.get_or_create(user=user)
            profile.role = udata['role']
            profile.phone_number = udata['phone']
            profile.save()

            created_users[udata['username']] = user
            status_txt = "Created" if created else "Updated"
            self.stdout.write(f"    [{status_txt}] {udata['username']} ({udata['role']}) - Pass: {udata['password']}")

        # -------------------------------------------------------------
        # 2. Create 8 Standard Categories
        # -------------------------------------------------------------
        self.stdout.write("\n--> Creating 8 Standard Campus Categories...")
        categories_data = [
            ("Electrical & Power", "Issues related to power outlets, lighting, ceiling fans, circuit breakers, and power supply."),
            ("Plumbing & Water Supply", "Leaking taps, clogged drains, washroom water supply, water purifier, and pipe repairs."),
            ("Network & Internet", "Wi-Fi connectivity, LAN ethernet ports, firewall restrictions, and router issues."),
            ("Furniture & Carpentry", "Broken desks, chairs, damaged doors, window latches, locks, and whiteboard fixtures."),
            ("Air Conditioning & Ventilation", "AC not cooling, remote malfunction, exhaust fans, and classroom airflow issues."),
            ("Cleanliness & Sanitation", "Waste disposal, washroom cleaning, corridor hygiene, and pest control."),
            ("Security & Safety", "CCTV issues, gate access, lighting in isolated campus areas, and fire safety equipment."),
            ("Infrastructure & Maintenance", "Wall cracks, water seepage, ceiling leaks, elevator operation, and pathway paving."),
        ]

        created_categories = {}
        for cat_name, cat_desc in categories_data:
            cat, created = Category.objects.get_or_create(
                name=cat_name,
                defaults={'description': cat_desc, 'is_active': True}
            )
            created_categories[cat_name] = cat
            status_txt = "Created" if created else "Existing"
            self.stdout.write(f"    [{status_txt}] {cat_name}")

        # -------------------------------------------------------------
        # 3. Create Sample Complaints across all Lifecycle States
        # -------------------------------------------------------------
        self.stdout.write("\n--> Creating 18 Sample Complaints across all Lifecycle States...")

        now = timezone.now()

        sample_complaints = [
            # ---------------- SUBMITTED (4 tickets) ----------------
            {
                "title": "Ceiling Fan Screeching Loudly in Seminar Hall",
                "category": "Electrical & Power",
                "priority": Complaint.PRIORITY_MEDIUM,
                "location": "Seminar Complex, Hall 201",
                "description": "The third ceiling fan from the entrance produces an unbearable high-pitched screeching sound when running above speed 2, disrupting ongoing lectures.",
                "submitted_by": "student1",
                "status": Complaint.STATUS_SUBMITTED,
                "created_offset_hours": 3,
            },
            {
                "title": "Frequent Wi-Fi Disconnections in Central Library",
                "category": "Network & Internet",
                "priority": Complaint.PRIORITY_HIGH,
                "location": "Central Library, 2nd Floor Digital Study Area",
                "description": "The campus Wi-Fi access point 'LIB-AP-04' constantly drops connections every 5-10 minutes, making online research and assignment submissions difficult.",
                "submitted_by": "student2",
                "status": Complaint.STATUS_SUBMITTED,
                "created_offset_hours": 5,
            },
            {
                "title": "Water Cooler Dispensing Lukewarm Water",
                "category": "Plumbing & Water Supply",
                "priority": Complaint.PRIORITY_LOW,
                "location": "Hostel Block C, Ground Floor Common Area",
                "description": "The RO drinking water cooler has stopped cooling since yesterday afternoon. Water is flowing but not chilled.",
                "submitted_by": "student3",
                "status": Complaint.STATUS_SUBMITTED,
                "created_offset_hours": 8,
            },
            {
                "title": "Broken Handle on Emergency Exit Door",
                "category": "Security & Safety",
                "priority": Complaint.PRIORITY_URGENT,
                "location": "Science Block A, West Stairwell",
                "description": "The emergency exit push bar handle is jammed from the inside and will not unlatch easily. This poses an immediate fire escape safety hazard.",
                "submitted_by": "student1",
                "status": Complaint.STATUS_SUBMITTED,
                "created_offset_hours": 2,
            },

            # ---------------- ASSIGNED (3 tickets) ----------------
            {
                "title": "Overhead Projector Power Cord Shorted",
                "category": "Electrical & Power",
                "priority": Complaint.PRIORITY_HIGH,
                "location": "Academic Block 1, Classroom 104",
                "description": "The ceiling-mounted projector sparked when powered on this morning and is currently completely unresponsive.",
                "submitted_by": "student1",
                "assigned_to": "staff1",
                "status": Complaint.STATUS_ASSIGNED,
                "created_offset_hours": 24,
                "assigned_offset_hours": 20,
                "assign_remark": "Assigned to Electrical maintenance team for immediate replacement of power supply unit.",
            },
            {
                "title": "Overflowing Washroom Basin Drain",
                "category": "Plumbing & Water Supply",
                "priority": Complaint.PRIORITY_URGENT,
                "location": "Mechanical Engineering Block, 1st Floor Restroom",
                "description": "The center washbasin drain is completely blocked and water is overflowing onto the floor creating slippery conditions.",
                "submitted_by": "student2",
                "assigned_to": "staff2",
                "status": Complaint.STATUS_ASSIGNED,
                "created_offset_hours": 18,
                "assigned_offset_hours": 16,
                "assign_remark": "Assigned to Plumbing team with high priority drain cleaning request.",
            },
            {
                "title": "AC Unit Leaking Water onto Lecture Desks",
                "category": "Air Conditioning & Ventilation",
                "priority": Complaint.PRIORITY_MEDIUM,
                "location": "Management Studies Complex, Room 302",
                "description": "Condensation water is dripping steadily from the indoor split AC unit directly onto the students' seating row below.",
                "submitted_by": "student3",
                "assigned_to": "staff1",
                "status": Complaint.STATUS_ASSIGNED,
                "created_offset_hours": 30,
                "assigned_offset_hours": 26,
                "assign_remark": "Assigned to HVAC technician for drain pipe inspection.",
            },

            # ---------------- IN_PROGRESS (4 tickets) ----------------
            {
                "title": "Broken Window Latch Causing Rain Ingress",
                "category": "Furniture & Carpentry",
                "priority": Complaint.PRIORITY_MEDIUM,
                "location": "Civil Engineering Lab 2, Window 3",
                "description": "The aluminum window latch is broken off and cannot be latched shut. During heavy wind/rain, moisture enters the computer simulation lab.",
                "submitted_by": "student1",
                "assigned_to": "staff2",
                "status": Complaint.STATUS_IN_PROGRESS,
                "created_offset_hours": 48,
                "assigned_offset_hours": 40,
                "in_progress_offset_hours": 12,
                "assign_remark": "Assigned to carpentry workshop for hardware replacement.",
                "progress_remark": "Technician visited site, measured replacement latch specs, and ordered replacement hardware from inventory.",
            },
            {
                "title": "LAN Port Not Functioning at Workstation 18",
                "category": "Network & Internet",
                "priority": Complaint.PRIORITY_LOW,
                "location": "Computer Center Lab 4, Desk 18",
                "description": "The RJ-45 wall socket does not register any ethernet connection link light when plugged into test PCs.",
                "submitted_by": "student2",
                "assigned_to": "staff1",
                "status": Complaint.STATUS_IN_PROGRESS,
                "created_offset_hours": 36,
                "assigned_offset_hours": 30,
                "in_progress_offset_hours": 8,
                "assign_remark": "Assigned to Network Operations technician.",
                "progress_remark": "Testing line with cable tracer; suspect crimping failure in patch panel.",
            },
            {
                "title": "Water Pipe Seepage near Hostel Dining Area",
                "category": "Plumbing & Water Supply",
                "priority": Complaint.PRIORITY_HIGH,
                "location": "Mess Hall Corridor, Dining Block A",
                "description": "Damp patches and visible water seepage running along the baseboard outside the dining hall service entrance.",
                "submitted_by": "student3",
                "assigned_to": "staff2",
                "status": Complaint.STATUS_IN_PROGRESS,
                "created_offset_hours": 60,
                "assigned_offset_hours": 48,
                "in_progress_offset_hours": 18,
                "assign_remark": "Assigned to plumbing maintenance team.",
                "progress_remark": "Isolated main supply line; excavation of concealed valve initiated to replace cracked joint.",
            },
            {
                "title": "Staircase Emergency Lighting Battery Fault",
                "category": "Security & Safety",
                "priority": Complaint.PRIORITY_HIGH,
                "location": "Hostel Block B, South Fire Exit Stairway",
                "description": "The emergency exit LED backup light flashes amber indicating battery failure during power transitions.",
                "submitted_by": "student1",
                "assigned_to": "staff1",
                "status": Complaint.STATUS_IN_PROGRESS,
                "created_offset_hours": 40,
                "assigned_offset_hours": 32,
                "in_progress_offset_hours": 10,
                "assign_remark": "Assigned to Electrical Safety team.",
                "progress_remark": "Procured 12V backup battery replacement; installation underway.",
            },

            # ---------------- RESOLVED (4 tickets) ----------------
            {
                "title": "Classroom 205 Wi-Fi Router Offline",
                "category": "Network & Internet",
                "priority": Complaint.PRIORITY_HIGH,
                "location": "Academic Block 2, Room 205",
                "description": "Entire room unable to connect to campus network due to router power indicator being dark.",
                "submitted_by": "student2",
                "assigned_to": "staff1",
                "status": Complaint.STATUS_RESOLVED,
                "created_offset_hours": 72,
                "assigned_offset_hours": 60,
                "in_progress_offset_hours": 36,
                "resolved_offset_hours": 6,
                "assign_remark": "Assigned to IT Network team.",
                "progress_remark": "Investigating PoE adapter switch port failure.",
                "resolved_remark": "Replaced faulty PoE injector and reset access point firmware. Verified 100Mbps connection speed.",
            },
            {
                "title": "Cafeteria Exhaust Fan Motor Seized",
                "category": "Air Conditioning & Ventilation",
                "priority": Complaint.PRIORITY_HIGH,
                "location": "Student Cafeteria, Kitchen Area",
                "description": "Main kitchen exhaust fan stopped spinning, causing smoke accumulation in the food prep area.",
                "submitted_by": "student3",
                "assigned_to": "staff2",
                "status": Complaint.STATUS_RESOLVED,
                "created_offset_hours": 80,
                "assigned_offset_hours": 68,
                "in_progress_offset_hours": 40,
                "resolved_offset_hours": 12,
                "assign_remark": "Assigned to HVAC team for urgent motor replacement.",
                "progress_remark": "New exhaust motor mounted, testing belt tension.",
                "resolved_remark": "Replaced burned fan capacitor and lubricated bearings. Fan is operating at full CFM capacity.",
            },
            {
                "title": "Damaged Whiteboard Surface in Tutorial Room",
                "category": "Furniture & Carpentry",
                "priority": Complaint.PRIORITY_LOW,
                "location": "Block 3, Tutorial Room T-12",
                "description": "Whiteboard has permanent ink staining and deep scratches that cannot be erased.",
                "submitted_by": "student1",
                "assigned_to": "staff1",
                "status": Complaint.STATUS_RESOLVED,
                "created_offset_hours": 96,
                "assigned_offset_hours": 84,
                "in_progress_offset_hours": 50,
                "resolved_offset_hours": 14,
                "assign_remark": "Assigned to carpentry / facility maintenance.",
                "progress_remark": "Removed old board, resurfacing mounting brackets.",
                "resolved_remark": "Installed brand new 8x4 magnetic melamine whiteboard with marker tray.",
            },
            {
                "title": "Corridor Dustbin Broken and Overflowing",
                "category": "Cleanliness & Sanitation",
                "priority": Complaint.PRIORITY_MEDIUM,
                "location": "Hostel Block A, 3rd Floor Corridor",
                "description": "Plastic pedal dustbin is cracked at base and overflowing, causing trash on walkway.",
                "submitted_by": "student2",
                "assigned_to": "staff2",
                "status": Complaint.STATUS_RESOLVED,
                "created_offset_hours": 48,
                "assigned_offset_hours": 36,
                "in_progress_offset_hours": 24,
                "resolved_offset_hours": 4,
                "assign_remark": "Assigned to Sanitation supervisor.",
                "progress_remark": "Cleaning staff dispatched for waste clearance.",
                "resolved_remark": "Cleared all refuse, disinfected floor, and placed two new segregated color-coded dustbins.",
            },

            # ---------------- CLOSED (3 tickets) ----------------
            {
                "title": "Defective Switchboard in Mechanical Workshop",
                "category": "Electrical & Power",
                "priority": Complaint.PRIORITY_HIGH,
                "location": "Mechanical Workshop Shed B, Lathe Area",
                "description": "3-phase power socket switch had loose contact causing intermittent sparks during machine startup.",
                "submitted_by": "student1",
                "assigned_to": "staff1",
                "status": Complaint.STATUS_CLOSED,
                "created_offset_hours": 140,
                "assigned_offset_hours": 120,
                "in_progress_offset_hours": 90,
                "resolved_offset_hours": 48,
                "closed_offset_hours": 24,
                "assign_remark": "Assigned to senior electrician.",
                "progress_remark": "Rewiring 32A industrial breaker socket.",
                "resolved_remark": "Replaced entire modular switchboard with heavy-duty IP65 enclosure. Voltage load tested at 415V.",
                "closed_remark": "Verified by student. Lathes are running safely without sparks.",
            },
            {
                "title": "Damaged Classroom Chair in Lecture Hall 4",
                "category": "Furniture & Carpentry",
                "priority": Complaint.PRIORITY_LOW,
                "location": "Lecture Hall Complex, Hall 4, Row D Seat 12",
                "description": "Armrest writing tablet is cracked and detached from student desk chair.",
                "submitted_by": "student2",
                "assigned_to": "staff2",
                "status": Complaint.STATUS_CLOSED,
                "created_offset_hours": 160,
                "assigned_offset_hours": 140,
                "in_progress_offset_hours": 110,
                "resolved_offset_hours": 70,
                "closed_offset_hours": 30,
                "assign_remark": "Assigned to furniture maintenance.",
                "progress_remark": "Welding support frame and fitting new wooden tablet.",
                "resolved_remark": "Refitted reinforced writing pad and tightened all base bolts.",
                "closed_remark": "Student verified and closed complaint. Chair is fully functional.",
            },
            {
                "title": "Plaster Flaking and Ceiling Water Stain",
                "category": "Infrastructure & Maintenance",
                "priority": Complaint.PRIORITY_MEDIUM,
                "location": "Old Academic Block, Staff Room 108",
                "description": "Water stain on false ceiling tiles and flaking plaster falling onto office corner.",
                "submitted_by": "student3",
                "assigned_to": "staff1",
                "status": Complaint.STATUS_CLOSED,
                "created_offset_hours": 180,
                "assigned_offset_hours": 160,
                "in_progress_offset_hours": 130,
                "resolved_offset_hours": 80,
                "closed_offset_hours": 35,
                "assign_remark": "Assigned to civil works team.",
                "progress_remark": "Roof waterproof membrane patch applied above staff room.",
                "resolved_remark": "Waterproofing complete, replaced 4 stained ceiling tiles, repainted plaster with anti-fungal emulsion.",
                "closed_remark": "Administrator verified and closed ticket following leak test.",
            },
        ]

        admin_user = created_users['admin']

        for cdata in sample_complaints:
            cat_obj = created_categories[cdata['category']]
            student_user = created_users[cdata['submitted_by']]
            assigned_user = created_users.get(cdata.get('assigned_to'))
            
            created_at = now - timedelta(hours=cdata['created_offset_hours'])
            
            resolved_at = None
            if 'resolved_offset_hours' in cdata:
                resolved_at = now - timedelta(hours=cdata['resolved_offset_hours'])
                
            closed_at = None
            if 'closed_offset_hours' in cdata:
                closed_at = now - timedelta(hours=cdata['closed_offset_hours'])

            # Create complaint directly
            complaint = Complaint(
                title=cdata['title'],
                category=cat_obj,
                priority=cdata['priority'],
                location=cdata['location'],
                description=cdata['description'],
                submitted_by=student_user,
                assigned_to=assigned_user,
                status=cdata['status'],
                resolved_at=resolved_at,
                closed_at=closed_at,
            )
            # Save without triggering auto-transition
            complaint.save()

            # Override timestamps to match realistic timeline
            Complaint.objects.filter(id=complaint.id).update(
                created_at=created_at,
                updated_at=closed_at or resolved_at or (now - timedelta(hours=cdata.get('in_progress_offset_hours', cdata['created_offset_hours'])))
            )

            # Build realistic audit trail (ComplaintHistory)
            # 1. Initial Submission
            h1 = ComplaintHistory.objects.create(
                complaint=complaint,
                old_status=Complaint.STATUS_SUBMITTED,
                new_status=Complaint.STATUS_SUBMITTED,
                changed_by=student_user,
                remarks="Complaint registered by student."
            )
            ComplaintHistory.objects.filter(id=h1.id).update(changed_at=created_at)

            # 2. Assignment
            if cdata['status'] in [Complaint.STATUS_ASSIGNED, Complaint.STATUS_IN_PROGRESS, Complaint.STATUS_RESOLVED, Complaint.STATUS_CLOSED]:
                assigned_time = now - timedelta(hours=cdata['assigned_offset_hours'])
                h2 = ComplaintHistory.objects.create(
                    complaint=complaint,
                    old_status=Complaint.STATUS_SUBMITTED,
                    new_status=Complaint.STATUS_ASSIGNED,
                    changed_by=admin_user,
                    remarks=cdata.get('assign_remark', f"Assigned to {assigned_user.get_full_name()} for maintenance.")
                )
                ComplaintHistory.objects.filter(id=h2.id).update(changed_at=assigned_time)

            # 3. In Progress
            if cdata['status'] in [Complaint.STATUS_IN_PROGRESS, Complaint.STATUS_RESOLVED, Complaint.STATUS_CLOSED]:
                progress_time = now - timedelta(hours=cdata['in_progress_offset_hours'])
                h3 = ComplaintHistory.objects.create(
                    complaint=complaint,
                    old_status=Complaint.STATUS_ASSIGNED,
                    new_status=Complaint.STATUS_IN_PROGRESS,
                    changed_by=assigned_user,
                    remarks=cdata.get('progress_remark', "Technician started inspection and maintenance work.")
                )
                ComplaintHistory.objects.filter(id=h3.id).update(changed_at=progress_time)

            # 4. Resolved
            if cdata['status'] in [Complaint.STATUS_RESOLVED, Complaint.STATUS_CLOSED]:
                resolved_time = now - timedelta(hours=cdata['resolved_offset_hours'])
                h4 = ComplaintHistory.objects.create(
                    complaint=complaint,
                    old_status=Complaint.STATUS_IN_PROGRESS,
                    new_status=Complaint.STATUS_RESOLVED,
                    changed_by=assigned_user,
                    remarks=cdata.get('resolved_remark', "Issue resolved successfully.")
                )
                ComplaintHistory.objects.filter(id=h4.id).update(changed_at=resolved_time)

            # 5. Closed
            if cdata['status'] == Complaint.STATUS_CLOSED:
                closed_time = now - timedelta(hours=cdata['closed_offset_hours'])
                h5 = ComplaintHistory.objects.create(
                    complaint=complaint,
                    old_status=Complaint.STATUS_RESOLVED,
                    new_status=Complaint.STATUS_CLOSED,
                    changed_by=student_user if 'student' in cdata['closed_remark'].lower() else admin_user,
                    remarks=cdata.get('closed_remark', "Resolution confirmed. Ticket officially closed.")
                )
                ComplaintHistory.objects.filter(id=h5.id).update(changed_at=closed_time)

            self.stdout.write(f"    [{complaint.complaint_id}] {complaint.status:<12} | {complaint.priority:<6} | {complaint.title[:45]}")

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] Successfully seeded demo dataset!"))
        self.stdout.write(self.style.MIGRATE_LABEL("You can now run: python manage.py runserver"))
