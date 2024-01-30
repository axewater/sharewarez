

@bp.route('/add_to_whitelist', methods=['GET'])
def add_to_whitelist():
    if request.args.get('password') != 'your_admin_password':
        abort(403)
    emails = ["maupie@gmail.com", "wateraxe@gmail.com", "ilonabogusz2@gmail.com"]  # Add your emails here
    added_emails = []
    existing_emails = []

    for email in emails:
        entry = Whitelist.query.filter_by(email=email).first()
        if entry:
            existing_emails.append(email)
        else:
            new_entry = Whitelist(email=email)
            db.session.add(new_entry)
            added_emails.append(email)

    try:
        db.session.commit()
    except Exception as e:
        error_message = "An error occurred while adding emails to the whitelist."
        print(f"Error: {e}")
        return error_message, 500

    message = "Emails added successfully."
    if added_emails:
        message += f" Added emails: {', '.join(added_emails)}"
    if existing_emails:
        message += f" Emails already exist: {', '.join(existing_emails)}"

    return message, 200


@bp.route('/add_to_blacklist', methods=['GET'])
def add_to_blacklist():
    if request.args.get('password') != 'your_admin_password':
        abort(403)
    banned_names = ["John Doe", "Jane Smith", "Alice Wonderland"]  # Add your banned names here
    added_names = []
    existing_names = []

    for name in banned_names:
        entry = Blacklist.query.filter_by(banned_name=name).first()
        if entry:
            existing_names.append(name)
        else:
            new_entry = Blacklist(banned_name=name)
            db.session.add(new_entry)
            added_names.append(name)

    try:
        db.session.commit()
    except Exception as e:
        error_message = "An error occurred while adding names to the blacklist."
        print(f"Error: {e}")
        return error_message, 500

    message = "Names added successfully."
    if added_names:
        message += f" Added names: {', '.join(added_names)}"
    if existing_names:
        message += f" Names already exist: {', '.join(existing_names)}"

    return message, 200
