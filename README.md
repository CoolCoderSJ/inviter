If you're familiar with github organizations, you'll know you can only invite someone by username or email. **But what if you don't know either?**

**Inviter lets you create invitation links for github organizations** to solve this. Simply send someone the invite link, and inviter will authenticate them and add them to your organizaion and team automatically.

## The flow
1. You create an invitation link for your organization (and optionally, any team(s))
2. You send the link to the person you want to invite
3. They click the link, authenticate with github, and are shown a confirmation
    a. The confirmation page will show them the organization and team they're being invited to, and ask them to confirm
4. They confirm, and are sent an invitation to the organization and team
    a. As a bonus, Inviter checks whether they're already a member and won't bother trying to send another invitation if they are.
5. They are then redirected directly to Github's invitation page, where they'll be one-click away from accepting (rather than having to navigate to github/their email themselves)

## Self hosting
1. Clone the repo
2. `pip install -r requirements.txt`
3. Mongodb is required. You can run it locally or use a service like Atlas
4. Copy `.env.example` to `.env` and fill in the required fields
5. `python main.py`