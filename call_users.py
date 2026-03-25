from twilio_call import call_user

# List of numbers to call (E.164 format)
numbers = ["+919882397989","+917018487497"]

for num in numbers:
    call_user(num)
