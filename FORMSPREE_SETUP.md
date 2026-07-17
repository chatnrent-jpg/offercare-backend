# Formspree Setup - Get Your Form Working in 2 Minutes

**Zero backend code required!** Formspree handles all email submissions for free.

---

## 🚀 Step 1: Get Your Formspree Form ID (1 minute)

### Option A: Free Tier (50 submissions/month)
1. Go to https://formspree.io
2. Click "Get Started" or "Sign Up"
3. Create account (GitHub/Google/Email)
4. Click "New Form"
5. **Copy your Form ID** (looks like `YOUR_FORM_ID`)

### Option B: Use Email Directly (No signup)
1. Replace `YOUR_FORM_ID` with your email address:
   ```html
   action="https://formspree.io/f/your-email@company.com"
   ```
2. **First submission will require confirmation** (one-time)

---

## 🔧 Step 2: Update Your Landing Page (30 seconds)

### Open your `index.html` file
Find line 60 (the form action):

```html
action="https://formspree.io/f/YOUR_FORM_ID"
```

### Replace with YOUR actual Form ID:

**Option 1: Formspree Dashboard ID**
```html
action="https://formspree.io/f/xpzgabcd"
```

**Option 2: Direct Email**
```html
action="https://formspree.io/f/your-email@company.com"
```

**Save the file!**

---

## ✅ Step 3: Test Your Form (30 seconds)

1. **Refresh your browser** (http://localhost:8080)
2. Enter your email in the form
3. Click "Request Priority Access"
4. **Check your email** for confirmation (if using email directly)
5. **Check Formspree dashboard** for submissions

---

## 📊 What You Get with Formspree

### Free Tier
- ✅ 50 submissions per month
- ✅ Email notifications
- ✅ CSV export
- ✅ Spam filtering
- ✅ File uploads (if needed)

### Paid Tier ($10/month)
- ✅ 1,000 submissions per month
- ✅ Custom thank you page
- ✅ Webhook integration
- ✅ Archive all submissions
- ✅ Remove Formspree branding

---

## 🎯 Enhanced Features Already Built In

Your form now includes:

### 1. **Hidden Context Fields**
```html
<input type="hidden" name="_subject" value="New VettedPay Waitlist Signup!">
<input type="hidden" name="page" value="landing">
<input type="hidden" name="timestamp" id="timestampInput">
<input type="hidden" name="referral" id="referralInput">
```

**You'll receive emails with**:
- ✉️ Email address
- 📄 Page: "landing"
- 🕐 Timestamp: Exact signup time
- 🔗 Referral: Source (organic, twitter, etc.)

### 2. **Referral Tracking**
Automatically captures:
- `?ref=twitter` → Tracks Twitter signups
- `?ref=producthunt` → Tracks Product Hunt
- `?ref=linkedin` → Tracks LinkedIn
- No `?ref=` → Tracks as "organic"

### 3. **Visual Feedback**
- ⏳ "Joining..." loading state
- ✓ Success message with animation
- ❌ Error handling (if email invalid)
- 📧 Email validation (business email format)

### 4. **Prevent Double Submission**
- Button disables after click
- Form hides after success
- Success display shows confirmation

---

## 📧 Email Notifications

### What You'll Receive
```
Subject: New VettedPay Waitlist Signup!

Email: user@company.com
Page: landing
Timestamp: 2026-07-17T14:00:00Z
Referral: twitter
```

### Customize Email Subject
Update line 70 in `index.html`:
```html
<input type="hidden" name="_subject" value="🚀 New VettedPay Alpha Request">
```

---

## 🔄 Alternative Form Handlers (If Needed)

### Basin (Formspree Alternative)
- **URL**: https://usebasin.com
- **Free**: 100 submissions/month
- **Setup**: Similar to Formspree

### Netlify Forms (If Deploying to Netlify)
```html
<form name="waitlist" method="POST" data-netlify="true">
  <!-- Your form fields -->
</form>
```
**Automatic integration** - no other setup needed!

### Web3Forms (Completely Free)
- **URL**: https://web3forms.com
- **Free**: Unlimited submissions
- **No account required** - just access key

---

## 🎨 Customization Options

### Redirect After Submission
Add this hidden field to redirect users after signup:
```html
<input type="hidden" name="_next" value="https://vettedpay.com/thank-you">
```

### Custom Confirmation Message
Add this hidden field:
```html
<input type="hidden" name="_confirmation" value="Thanks for joining! Check your email.">
```

### Honeypot (Spam Protection)
Already built-in! Formspree automatically filters spam.

---

## 🐛 Troubleshooting

### Issue: "Form submission failed"
**Solution**: 
1. Check your Form ID is correct
2. Verify internet connection
3. Try refreshing the page

### Issue: "Not receiving emails"
**Solution**:
1. Check spam folder
2. Verify email address in Formspree dashboard
3. Confirm form is submitting (check Formspree submissions)

### Issue: "Need to confirm email first"
**Solution**:
1. If using email directly, check inbox for confirmation link
2. Click confirmation link
3. Resubmit form

### Issue: "Want to connect to your own backend later"
**Solution**:
1. Keep Formspree for now (zero maintenance)
2. Later, just update the `action` URL to your API:
   ```html
   action="https://your-backend.com/api/v1/vettedpay/waitlist"
   ```

---

## 📈 Tracking Conversions

### See Your Signups
1. **Formspree Dashboard**: https://formspree.io/forms
2. **Email Notifications**: Every submission
3. **CSV Export**: Download all submissions

### Integration with Analytics (Optional)

#### Google Analytics
Add to your form submit handler (already in the code):
```javascript
gtag('event', 'generate_lead', {
  'event_category': 'Waitlist',
  'event_label': 'VettedPay Landing'
});
```

#### Mixpanel
```javascript
mixpanel.track('Waitlist Signup', {
  'source': 'landing_page',
  'referral': refSource
});
```

---

## 🎉 You're All Set!

### Quick Checklist
- [ ] Got Formspree Form ID from https://formspree.io
- [ ] Updated `action="https://formspree.io/f/YOUR_FORM_ID"` in index.html
- [ ] Saved the file
- [ ] Refreshed browser
- [ ] Tested form submission
- [ ] Checked email for confirmation

### What Happens Next
1. **Users fill out form** → Formspree receives data
2. **You get email notification** → "New VettedPay Waitlist Signup!"
3. **Data stored in Formspree** → Export as CSV anytime
4. **User sees success message** → "Welcome to the inner circle!"

---

## 🚀 Deploy When Ready

Once you've tested locally:

### Vercel
```bash
cd frontend/public
vercel --prod
```

### Netlify
Drag `frontend/public` folder to https://app.netlify.com/drop

**Your form will work immediately on production!** No configuration needed.

---

## 💡 Pro Tips

### Tip 1: Use Unique Subject Lines
Different subject for different campaigns:
```html
<input type="hidden" name="_subject" value="🎯 Product Hunt Launch Signup!">
```

### Tip 2: Track Campaign Success
Use referral parameter:
```
https://vettedpay.com?ref=producthunt
https://vettedpay.com?ref=twitter
https://vettedpay.com?ref=hackernews
```

### Tip 3: A/B Test Headlines
Track which headline converts better by adding:
```html
<input type="hidden" name="headline_variant" value="A">
```

---

## 📞 Need Help?

### Formspree Support
- Docs: https://help.formspree.io
- Email: support@formspree.io

### Quick Reference
- **Form ID Format**: `xpzgabcd` (8 characters)
- **Full URL**: `https://formspree.io/f/xpzgabcd`
- **Free Tier**: 50 submissions/month
- **Response Time**: Instant email notification

---

**Your landing page is now fully functional with zero backend code!** 🎉

