# Adjudication queue

73 of 200 golden cases were flagged during annotation as ambiguous 
or low-confidence. These are the cases where a single annotator's judgement is doing 
the most work, and where a second opinion changes the most.

For each: is the intent right? should it go to a human or can a bot answer it?

---

### G003  (labelled `delivery_delayed`, auto, confidence: medium)

> Amazon Logistics is a joke. They had 10 days to deliver a 📦 and blew it!

*Amazon actually replied:* That's not what we like to hear. When you have the chance, please send us your details directly here so we can look into this: <link>

*Why it was flagged:* Ten days late, framed as a swipe at Amazon Logistics. No E-rule fires on the opening.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G007  (labelled `billing_account`, ESCALATE, confidence: low)

> i am facing problem regarding my phone bill. And not able to contact amazon as they are unable to find my order.

*Amazon actually replied:* I understand your concern. We'll certainly help you with this. Kindly share your details here: <link> and we'll get it checked.

*Why it was flagged:* Phone-bill problem plus support unable to locate the order. Opening is vague.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G010  (labelled `service_complaint`, ESCALATE, confidence: medium)

> Not massively impressed - got home after a few days away to see my parcel had been delivered and left on my doorstep; I wasn't asked if this was ok. Seems that one of my lovely neighbours had also opened it for a peek - thankfully decided not to take anything. Not cool.

*Amazon actually replied:* Hi, sorry to hear that, do you have delivery preferences set on your account: <link>

*Why it was flagged:* Unattended doorstep delivery, neighbour opened it. Nothing lost, so not delivery_missing.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G017  (labelled `presales_info`, auto, confidence: medium)

> the echo show can you transfer tv programs/ from your phone to the echo show!?

*Amazon actually replied:* This is not a feature we currently have, but would love to get your feedback on this. Please reach out to us by e-mail at this link here: <link>

*Why it was flagged:* Echo Show capability question. Feature enquiry, not a fault.

*Definition used:* A question about products, policies, availability or how something works, with no existing order problem.

---

### G019  (labelled `billing_account`, ESCALATE, confidence: low)

> It's takes 40 minute to me to teach that - 1965*0.15 = 295 and not 283. I was weak student of maths but I am glad that software is weaker than mine !

*Amazon actually replied:* Sorry about your recent experience, Suchak. Could you please let us know what went wrong? We’ll fix it for you.

*Why it was flagged:* Discount miscalculated, partial Rs.15 refund, 40 minutes spent. Opening is hard to parse even for a human.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G021  (labelled `service_complaint`, ESCALATE, confidence: medium)

> Hey, thanks for AMZL leaving my packages unsecured outside of the CLOSED leasing office at my apt. I had to go on a hunt to find my damn packages. These other people are gonna have their stuff out all night unsecured too. <link>

*Amazon actually replied:* Whenever you have time please complete the form ^WT provided so my team can make sure this is escalated properly.

*Why it was flagged:* Packages left unsecured outside a closed leasing office; eventually found.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G023  (labelled `delivery_delayed`, auto, confidence: medium)

> I was determined to save my house 🌱 and got some fertilizer. Tell me why I've been waiting forever when I have prime

*Amazon actually replied:* So sorry for the delay! We are here to help! What is the current order status shown here: <link>

*Why it was flagged:* Opens as a delay; becomes delivered-not-received in turn two.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G024  (labelled `billing_account`, auto, confidence: medium)

> you sent me a 30 day free trial when i log in its trying to take payment of £7.99, thats not a 30 day free trial.

*Amazon actually replied:* Have you ever had a free trial of Amazon Prime in the past? As long as you are eligible for the trial, we won't charge you for the membership until the 30-day trial period has ended: <link>

*Why it was flagged:* Free-trial charge question answerable from published policy, so E2 explicitly does not fire.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G028  (labelled `feedback_other`, auto, confidence: medium)

> why offer a discount of Re 1? 🤔 <link>

*Amazon actually replied:* I understand your concern regarding the offer. However, this is the best price we could offer at this point of time.

*Why it was flagged:* Snark about a 1-rupee discount. Commentary rather than a request.

*Definition used:* Praise, thanks, suggestions, or non-actionable commentary.

---

### G029  (labelled `billing_account`, ESCALATE, confidence: medium)

> i think this might be fraudulent <link>

*Amazon actually replied:* Have you received an e-mail or text message from the e-mail address listed there? Please let us know.

*Why it was flagged:* Suspected phishing. Security-adjacent rather than the customer's own account; could be other.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G033  (labelled `delivery_delayed`, ESCALATE, confidence: medium)

> please help.... i was supposed to recieve something today and now it is showing that i need to put additional address. what should i do?

*Amazon actually replied:* I understand your concern regarding the delivery of your package. Please reach out to us here: <link> and we will help you.

*Why it was flagged:* Delivery blocked pending an address addition; needs an account-side change.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G034  (labelled `item_problem`, ESCALATE, confidence: medium)

> Hi ! Amazon has been my personal favorite but I was disappointed to know that when my friend ordered Samsung J7 Pro, a used Galaxy J7 was delivered by a #Amazonfulfilled seller called HeartySibling. Some help sorting this would be great. <link>

*Amazon actually replied:* We certainly didn't expect this to happen. Kindly report this to our support team via <link> so that we may look into it. Also, please don't provide your details, as we consider it to be personal info. Our Twitter page is visible to the public.

*Why it was flagged:* Used Galaxy J7 sent instead of a new J7 Pro by a fulfilled-by-Amazon seller.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G038  (labelled `billing_account`, auto, confidence: low)

> Never thought that Amazon will start fraudulent behavior. Selling product costing more than MRP(that too after discount). Order ID 408-1723980-9549101

*Amazon actually replied:* different M.R.P.s being used by manufacturers in different regions. Please don’t provide your details as we consider them to be personal information. Our Twitter page is public. 2/2

*Why it was flagged:* Price above MRP alleged as fraud. Amazon resolved with published MRP policy, so E2 does not fire by the written rule.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G040  (labelled `digital_service`, auto, confidence: low)

> . not sure why my account always seems to get disconnected. What’s up?

*Amazon actually replied:* Hrm, that is curious Elizabeth! What do you mean by 'disconnect' exactly? Are you losing connection? Also, which platform are you using to browse the website, PC or mobile? Plesae give us a little more info and we'd be happy to help.

*Why it was flagged:* 'Account gets disconnected' is underspecified: session/app fault vs account access. Amazon also had to ask.

*Definition used:* Amazon's own devices, apps, or digital services misbehaving.

---

### G041  (labelled `item_problem`, ESCALATE, confidence: medium)

> So my HD60 S from arrived today...oh wait, it was literally an empty box...but my order shows it as being delivered! Second time this has happened to me! <link>

*Amazon actually replied:* Oh no! I'm sorry to hear that you received an empty box. We are unable to view orders via Twitter, but we'd like to help! When you get a moment, please contact us via chat or phone: <link>

*Why it was flagged:* Empty box marked delivered, second occurrence. Sits between item_problem and delivery_missing.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G045  (labelled `delivery_delayed`, auto, confidence: low)

> Yo tell me how this happens?!? Now a one-in-a-lifetime holiday surprise is RUINED!!! #amazon #blatantlies <link>

*Amazon actually replied:* Oh no! I'm sorry your tracking shows your order arriving later than expected! We'd like to look into this with you and see what options we have available. Please reach us by phone or chat here: <link>

*Why it was flagged:* Angry, link-only evidence, ruined holiday gift. Anger not vulnerability, so no E6 by the written rule.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G046  (labelled `other`, ESCALATE, confidence: medium)

> #NORESOLUTIONAMAZON... <link>

*Amazon actually replied:* Could you confirm sharing your details here: <link> ?

*Why it was flagged:* Hashtag plus link. #NORESOLUTION signals an open complaint but there is no classifiable content.

*Definition used:* Unclear, off-topic, spam, or too little information to classify.

---

### G049  (labelled `digital_service`, auto, confidence: medium)

> Why did remove sorting options from their app? No more price sorting 😢 😒 <link>

*Amazon actually replied:* I've checked and see that the sorting option for prices is available. Once you search for a product in the app, you'll be able to the "Sort" option right below the search bar. Could you let us know where exactly you're facing the issue?

*Why it was flagged:* App sorting options removed. Reported as a fault, turned out to be a product decision.

*Definition used:* Amazon's own devices, apps, or digital services misbehaving.

---

### G050  (labelled `digital_service`, auto, confidence: medium)

> #NEWTON is exclusively streaming on . Watch it now: <link> <link> why is it not available for download? Why can't I download it and then watch while in commute Amazon? <link>

*Amazon actually replied:* The movie "Newton" is now available for download on Amazon Prime Video.

*Why it was flagged:* Prime Video download availability. Borderline presales_info.

*Definition used:* Amazon's own devices, apps, or digital services misbehaving.

---

### G052  (labelled `item_problem`, auto, confidence: medium)

> Welp, entire first round of purchases was destroyed in transit. Merry Christmas, kids!

*Amazon actually replied:* Oh no! That's horrible, Matthew. Were you able to find solutions for all the damaged items? You can look at options here: <link> Let us know if you need anything!

*Why it was flagged:* Multiple items damaged in transit. Returns flow is public; no E-rule fires at open.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G053  (labelled `other`, ESCALATE, confidence: medium)

> ACORDEI E 2 MINUTOS DEPOIS CHEGARAM OS MEUS LIVROS! OBRIGADA

*Amazon actually replied:* Que notícia maravilhosa, Tatá. Que bom que recebeu seu pedido tão rápido❣️🎉

*Why it was flagged:* Portuguese praise. All-caps with few function words, so the language filter missed it. Out of scope means route to the localised queue.

*Definition used:* Unclear, off-topic, spam, or too little information to classify.

---

### G054  (labelled `service_complaint`, ESCALATE, confidence: medium)

> your delivery service is a joke now. I am never receiving my items on time...and your customer service instead of helping are cancelling orders without asking if I want a refund or just information about my orders. A lot of customers will drop their membership soon.

*Amazon actually replied:* I'm sorry for the trouble. We're here to help! Do you have a current order you are having delivery issues with found here: <link>

*Why it was flagged:* Mixes chronic lateness with CS cancelling orders unasked. Could defensibly be delivery_delayed.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G056  (labelled `service_complaint`, ESCALATE, confidence: low)

> Dear I think it’s bad business to attempt a delivery at 5:40am as these aren’t business hours. Then saying it won’t be delivers until Tue 11/28?!? WTH

*Amazon actually replied:* Hello, I am sorry to hear about the delivery attempt taking place at that time. Do reach out to us if the parcel is not with you by the date provided.

*Why it was flagged:* 5:40am delivery attempt then a four-day slip. Carrier conduct plus delay.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G060  (labelled `delivery_delayed`, auto, confidence: medium)

> Already waited for 6 days and now amazon says it will take 1 more day of expected. Vry bad delivery while flipkart deliver product in max 4 days.. it shows wrongly unable to contact. Boy denied to deliver today to me when I called

*Amazon actually replied:* Sorry to know that you haven't received your order yet. Kindly contact us here: <link> and we'll get it checked for you.

*Why it was flagged:* Six days late and the driver personally refused to deliver. Contact was with the driver, not support, so E5 does not fire by the written rule.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G061  (labelled `feedback_other`, auto, confidence: low)

> I found only two Kannada movies in Amazon prime video, is in this way you will serve Kannadiga customers? Kannada is one of the oldest classical language, your way of respecting it is ignominious.

*Amazon actually replied:* We’re really sorry for the inconvenience. We’re constantly adding new content to our library. Stay tuned to our website for new updates.

*Why it was flagged:* Angry content-catalogue feedback. Non-actionable, but tone pushes toward service_complaint.

*Definition used:* Praise, thanks, suggestions, or non-actionable commentary.

---

### G063  (labelled `delivery_delayed`, auto, confidence: medium)

> One package just not delivered this week and one not delivered in 2 days and still MIA. Anyone know why I pay fro prime? what’s going on? <link>

*Amazon actually replied:* I'm really sorry that your order was delayed, Alyssa! If by chance the order does not arrive by the 16th as listed currently, please get back with us so that we can assist in resolving the matter.

*Why it was flagged:* Two orders late, one described as MIA. Amazon handled as delayed.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G066  (labelled `delivery_delayed`, auto, confidence: medium)

> hey AMAZON..PET PAVILION gifts SUCK! I order an item 3 WEEKS ago, I get an email TODAY saying “SORRY it’ll be another WEEK!”

*Amazon actually replied:* I'm sorry for the frustration.​ Please keep us updated on your package delivery. We're here to help!

*Why it was flagged:* Three weeks late plus another week. Severe, but no E-rule fires on the opening text alone.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G068  (labelled `service_complaint`, ESCALATE, confidence: low)

> I’m tired of you guys not picking up your old fresh boxes when you drop new ones off

*Amazon actually replied:* I'm so sorry for the frustration, Fred! We'd like to help! You can request a pick up for the bags here: <link>

*Why it was flagged:* Fresh boxes not collected. Clear case of the policy over-escalating - a self-serve link resolved it.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G072  (labelled `digital_service`, auto, confidence: medium)

> is there a way to block a specific station when using Amazon Music with Alexa?

*Amazon actually replied:* Great question! Blocking specific stations isn't currently supported. However, you can you send us your feedback or any requests via Help &amp; Feedback in your Alexa app, details: <link>

*Why it was flagged:* Can a station be blocked on Alexa - capability question about an owned device.

*Definition used:* Amazon's own devices, apps, or digital services misbehaving.

---

### G074  (labelled `service_complaint`, ESCALATE, confidence: medium)

> Don’t know why I bother ordering anything with anymore, they can never deliver on time 🙄

*Amazon actually replied:* Hi, are you waiting on a delivery at the moment? What delivery date is listed in your order confirmation email?

*Why it was flagged:* 'They can never deliver on time' - chronic, no single order named at open.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G077  (labelled `delivery_missing`, ESCALATE, confidence: medium)

> like I'd really give these people a key to my house ... they can't even find it! No point in Prime when #amzl_us is delivering. In one week = lost 1 package and others (below) sitting at local station for 24 hrs and counting bc no delivery person to get to the customer. <link>

*Amazon actually replied:* So sorry to hear about the issues! Our team would like to look into this situation with you further, can you please provide your details here so that we can reach out? <link>

*Why it was flagged:* One package lost, others stranded at the depot; supervisor already involved.

*Definition used:* Order is recorded as delivered, or is lost, or went to the wrong place -- customer does not have it.

---

### G079  (labelled `service_complaint`, ESCALATE, confidence: low)

> I wish y’all wouldn’t use ...They always screw up

*Amazon actually replied:* I'm sorry for the trouble with delivery. Has the delivery date passed on your order: <link>

*Why it was flagged:* Opens as a carrier gripe with no request; a specific delayed order only emerges later.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G080  (labelled `digital_service`, auto, confidence: medium)

> Hello, trying to place an order in <link> (was given a $ gift voucher) and I want it delivering to a locker, but it keeps asking me to select a residential address in the UK, I need to select a locker but the option isn't available. Thanks in advance

*Amazon actually replied:* The option to deliver to a locker is only present when this option is available. If you are not seeing the option, then it is not available for this order.

*Why it was flagged:* Locker option missing at checkout on the .com store with a UK account.

*Definition used:* Amazon's own devices, apps, or digital services misbehaving.

---

### G083  (labelled `service_complaint`, ESCALATE, confidence: low)

> Not so cool to delay shipping a package and then just leave it between the doors when the video game could have fit in my door’s mail slot. <link>

*Amazon actually replied:* I'm sorry for this issue with how your order was delivered. Who was the carrier listed for the order: <link>

*Why it was flagged:* Item was delivered; complaint is about carrier handling and placement.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G086  (labelled `item_problem`, auto, confidence: medium)

> Someday will send me a Funko Pop that isn’t in a crushed box. I think. Maybe. <link>

*Amazon actually replied:* I'm sorry to see this! Please check here: <link> for replacement/refund options!

*Why it was flagged:* Wry recurring complaint about crushed collectible boxes.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G087  (labelled `service_complaint`, ESCALATE, confidence: low)

> I can’t believe how brands outright lie to their consumers

*Amazon actually replied:* Looks like you have faced some trouble, Gautamm. Could you please let us know what went wrong so that we can assist you accordingly ?

*Why it was flagged:* 'Brands outright lie to their consumers' with no specifics until turn two.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G089  (labelled `presales_info`, auto, confidence: medium)

> it is a joke or what? Why should prime customers pay Rs. 20. What is the use of taking prime subscription? <link>

*Amazon actually replied:* As a prime member, you're being charged Rs. 20 for delivery of pantry orders. I'll be sure to pass on your feedback internally.

*Why it was flagged:* Why Prime members pay a pantry delivery fee - a fee-policy question in complaint clothing.

*Definition used:* A question about products, policies, availability or how something works, with no existing order problem.

---

### G091  (labelled `billing_account`, ESCALATE, confidence: medium)

> Hey,Special Amazon promo offers not given to me when I was purchased a smartphone on great Indian sale period.I tried but amazon &amp; idea but no response yet. <link>

*Amazon actually replied:* Apologies, did you report this to our customer service team about it?

*Why it was flagged:* Promotional credit never applied; support unresponsive since 29 Oct.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G105  (labelled `billing_account`, ESCALATE, confidence: medium)

> I tried to order 1300 worth books and now you guys are charging 1200 rupees for deliver so total 2500? really amazon? Can you resolve this issue? and i added pay balance of 1300, in order to resend to my bank, you said you will take 10 days. Help

*Amazon actually replied:* I'm sorry to see you disappointed, call us here: <link> &amp; we'll get this checked.

*Why it was flagged:* Amazon Pay balance being returned to bank + delivery-fee dispute. Money movement on a named account.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G109  (labelled `feedback_other`, auto, confidence: medium)

> I feel like I got played at least have some bubble wrap in there 😭😂 <link>

*Amazon actually replied:* Hey, Amy! Please be sure to leave packaging feedback by navigating to your order here: <link>

*Why it was flagged:* Joking packaging complaint. Would be item_problem if damage were claimed.

*Definition used:* Praise, thanks, suggestions, or non-actionable commentary.

---

### G114  (labelled `delivery_delayed`, ESCALATE, confidence: low)

> I have Inquiry about one of my orders order number is (#111-4231028-7354663) what happened why then are not sending it and I want to know are they charged me or no Best wishes Nasser

*Amazon actually replied:* Thanks for reaching out to us! We'd like to help, we just need a little more information. Did you receive a cancellation e-mail?

*Why it was flagged:* Order status plus 'was I charged'. Turned out to be a cancellation and refund.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G117  (labelled `delivery_delayed`, auto, confidence: medium)

> I ordered supplies from Amazon over a month ago, I didn’t know standard shipping meant my package would take the Oregon Trail

*Amazon actually replied:* Hello Michelle, we're sorry you have not received your order. What is the delivery date that was provided to you in your order confirmation email? Also, what is your order status currently showing? You can check your order status here: <link>

*Why it was flagged:* Over a month late. Severity alone does not trigger a written rule, which is arguably a policy gap.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G121  (labelled `return_refund`, ESCALATE, confidence: medium)

> My HORROR I buy a power bank (Rs. 599) -- it has a manufacturing defect -- I initiate replacement. Amazon gives me courier phone no. &amp; says mail it; we will refund max Rs. 100 as courier charges. Courier says power bank will be sent only by road at a cost of Rs. 800.

*Amazon actually replied:* I understand your concern, I’d like to help you; please fill this form: <link> and I’ll contact you soon.

*Why it was flagged:* Return shipping (Rs 800) exceeds the item price (Rs 599) against a Rs 100 cap. Core dispute is the return economics.

*Definition used:* Wants to return, cancel or exchange, or is chasing money that has not come back.

---

### G122  (labelled `digital_service`, auto, confidence: low)

> the audible books I've purchased/subscription aren't showing up in my spouses Amazon audible app. She's in my Amazon household.

*Amazon actually replied:* Hey there! I'm sorry for the trouble! While membership benefits are unable to be shared, you can share audio books with household members. To confirm, is your spouse included in your household: <link>

*Why it was flagged:* Audible content not shared across Household. Sits between digital_service and billing_account (subscription).

*Definition used:* Amazon's own devices, apps, or digital services misbehaving.

---

### G123  (labelled `billing_account`, ESCALATE, confidence: medium)

> Hi! I need help about an order that was cancelled without being charged, but now we have seen that it was charged but you told me that it wasn't, can you help me?

*Amazon actually replied:* Hi, we usually only charge when the order is dispatched. Is it possible you can see an authorisation on your statement: <link>

*Why it was flagged:* Charge on a cancelled order. Amazon actually resolved it publicly via the authorisation-hold policy - policy is conservative here.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G125  (labelled `service_complaint`, ESCALATE, confidence: high)

> It's no longer even remotely surprising when 's carrier lies about delivering packages. But their customer service's "eh, give it a day or so and see if it shows up"? Guess I will finally throw in the towel and not renew my Prime membership when it expires in January.

*Amazon actually replied:* I'm sorry for the poor experience! This isn't what we strive for, and I'm sorry we let you down. Please keep us posted on delivery, we want to make sure you get your package.

*Why it was flagged:* Carrier false-delivery plus a dismissive support answer, ending in a non-renewal decision.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G127  (labelled `return_refund`, ESCALATE, confidence: medium)

> Since when did it cost a fuck ton to send stuff back to !? Bye bye prime membership.. waste of money. Amazon have gotten more and more greedy by the month.

*Amazon actually replied:* Hey, are you having a problem with a return? Without divulging any personal information could you please explain your issue?

*Why it was flagged:* Return-cost policy question carried by an explicit churn threat.

*Definition used:* Wants to return, cancel or exchange, or is chasing money that has not come back.

---

### G130  (labelled `billing_account`, auto, confidence: medium)

> a little bit of a warning would be nice before you charge me for another year of prime membership plz ! Just a email would do !

*Amazon actually replied:* Was the auto-renew setting turned off? If not, any subscription or membership with auto-renew active will automatically charge again at the end of its cycle. If you no longer needed Prime, learn more about how to cancel here: <link>

*Why it was flagged:* Auto-renew warning complaint; answerable from published policy.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G131  (labelled `delivery_delayed`, auto, confidence: medium)

> plz expedite the delivery of my order placed by mob no- 8010757001. Its urgent, you guyz didnt even give me option to pay 1 day delivery charge as well. Its my first order with u. Dont brk my trust. reaching twitter almost brks it.

*Amazon actually replied:* I get your concern about the order, Talha. We ship &amp; deliver orders as per the estimates shared with you. Please wait till the estimates, I'm positive your order should be delivered soon. Appreciate your understanding.

*Why it was flagged:* Asks to expedite a first order. Amazon resolved with an estimates explanation.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G132  (labelled `presales_info`, auto, confidence: medium)

> . Your shipping charges are so high for many products. Why so?

*Amazon actually replied:* Shipping charges vary owing to multiple reasons. You can check details here : <link> . Hope this helps.

*Why it was flagged:* Why are shipping charges high - policy question with a complaint flavour.

*Definition used:* A question about products, policies, availability or how something works, with no existing order problem.

---

### G133  (labelled `service_complaint`, ESCALATE, confidence: medium)

> - It is really poor service or has your online chat support been hacked ?

*Amazon actually replied:* We are sorry for this issue. We would love to help. Without sharing personal or account information please give us more details.

*Why it was flagged:* Sarcastic opener about chat support; the missing package only surfaces in turn two.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G141  (labelled `item_problem`, auto, confidence: medium)

> worst service from Amazon. Bought this watch and got defected one. I am a regular user of Amazon but never expected this kind of service. Need to improve your service.

*Amazon actually replied:* I'm sorry you've received a defective product. Please report it to our support team here: <link> we'll look into it and help you.

*Why it was flagged:* Defective watch wrapped in service-complaint language; the actionable core is the faulty item.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G145  (labelled `delivery_missing`, ESCALATE, confidence: high)

> What gives ? Four packages in the last month, and NONE of them have made it to my home . . . Worst of all, you all don't seem to care. Just saying . . . Feeling like someone is getting too big for their own good. #AmazonSucks

*Amazon actually replied:* Oh no! I can certainly understand your frustration! We're here to help! Were all 4 packages shipped by the same carrier or different ones? You can find that information here: <link>

*Why it was flagged:* Four packages in a month, none arrived. Could read as service_complaint.

*Definition used:* Order is recorded as delivered, or is lost, or went to the wrong place -- customer does not have it.

---

### G147  (labelled `presales_info`, auto, confidence: medium)

> what is the bitrate of Saavn songs played over Amazon Echo?

*Amazon actually replied:* The Echo plays the best quality based on your network.

*Why it was flagged:* Audio bitrate spec question; how-it-works rather than a fault.

*Definition used:* A question about products, policies, availability or how something works, with no existing order problem.

---

### G151  (labelled `presales_info`, auto, confidence: low)

> What is the point of Unlimited? I have 121 books on my Goodreads list, and NONE of them is free through this program. I've had this trial for 15 minutes, and I'm frustrated in the extreme!

*Amazon actually replied:* Oh no! We'd love to assist with this. Could you explain what has happened?

*Why it was flagged:* What Kindle Unlimited actually includes, wrapped in frustration. Sits between presales_info and service_complaint.

*Definition used:* A question about products, policies, availability or how something works, with no existing order problem.

---

### G152  (labelled `other`, ESCALATE, confidence: low)

> oh why do you have to lie? <link>

*Amazon actually replied:* Hi Katie! Could you provide us some additional details (without sharing personal account information) on what's occurred? We're here to help in any way we can!

*Why it was flagged:* 'Why do you have to lie?' plus an image. Delivery context only emerges later.

*Definition used:* Unclear, off-topic, spam, or too little information to classify.

---

### G155  (labelled `item_problem`, auto, confidence: medium)

> How do I organise a replacement advent calendar before next Thursday? Delivered today and a door is missing?! <link>

*Amazon actually replied:* Hi Shawn! Was the item sold directly by Amazon or a seller?

*Why it was flagged:* Advent calendar delivered with a door missing; public returns centre handled it despite the deadline.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G156  (labelled `presales_info`, auto, confidence: medium)

> So, it's been a while I am noticing that products that are searched as eligible for cod are also shown as not available in cod in payment methods. Is it something like cod blocked for me or for my pin code? Or cod blocked for prime members.

*Amazon actually replied:* I understand your concern regarding cash on delivery. Due to certain courier constraints, cash on delivery is not available for all pincodes. We'd like to check this and confirm, kindly connect with us here: <link>

*Why it was flagged:* Why cash-on-delivery shows as eligible in search but not at checkout.

*Definition used:* A question about products, policies, availability or how something works, with no existing order problem.

---

### G157  (labelled `other`, ESCALATE, confidence: low)

> this doesn’t really count does it..? Seriously?? Look forward to trying to track this ffs. <link>

*Amazon actually replied:* I'm sorry for the trouble with your delivery. Please try the steps listed here: <link> If you're still unable to locate it, we can help here: <link>

*Why it was flagged:* Meaning lives in an attached image the pipeline cannot see. Text alone is sarcasm plus a link.

*Definition used:* Unclear, off-topic, spam, or too little information to classify.

---

### G158  (labelled `billing_account`, ESCALATE, confidence: medium)

> how do I unsubscribe from Kindle FreeTime if the Kindle is lost? See no options on the website.

*Amazon actually replied:* Hi Jeff! Please ge tin touch with us here: <link> We'll be glad to help!

*Why it was flagged:* Cancel a FreeTime subscription for a lost Kindle; needs account-side action.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G161  (labelled `presales_info`, auto, confidence: low)

> Does anyone know what this is? It's on my Kindle Fire home page every darn day but I can't find it <link>

*Amazon actually replied:* Great question! This is a wearable camera. You can find more details about this item here: <link>

*Why it was flagged:* Asking what a recurring item on the Fire home page is. Product question, not a device fault.

*Definition used:* A question about products, policies, availability or how something works, with no existing order problem.

---

### G167  (labelled `presales_info`, auto, confidence: medium)

> Does anybody know if Amazon Prime Music is working in India on the Fire Stick?

*Amazon actually replied:* Please click on the link here: <link> to check the available app's in Fire TV Stick.

*Why it was flagged:* Availability of Prime Music on Fire Stick in India.

*Definition used:* A question about products, policies, availability or how something works, with no existing order problem.

---

### G168  (labelled `digital_service`, auto, confidence: medium)

> Watch Arjun Reddy &amp; other Latest Telugu Movies only on Amazon Prime Video. Install the App to watch #ArjunReddy <link> First rectify your player streaming issue

*Amazon actually replied:* The issue has been resolved now, please let us know if you still face the issue.

*Why it was flagged:* Streaming player fault raised as a reply to a promo tweet.

*Definition used:* Amazon's own devices, apps, or digital services misbehaving.

---

### G173  (labelled `delivery_missing`, ESCALATE, confidence: medium)

> order id #405-4047538-8095512 suppose to deliver today but not. Fake reporting done regarding address not clear by courier. Person called on 18th and says packet will b deliverd on 19th &amp; my son is still waiting for his gift. #hopeless1stTime

*Amazon actually replied:* Please don't provide your order details, we consider it personal information. Our Twitter page is visible to public. ^VN (2/2)

*Why it was flagged:* Carrier logged a false 'address unclear'; child waiting on a gift.

*Definition used:* Order is recorded as delivered, or is lost, or went to the wrong place -- customer does not have it.

---

### G176  (labelled `digital_service`, ESCALATE, confidence: medium)

> hey on this page <link> the "sign in using alternative factors" link (which points to <link> is broken and leads to a 404. which is kinda frustrating as i need to reset my 2FA <link>

*Amazon actually replied:* I am sorry to heat this. Can you please try clearing your cookies and cache as this may rectify this issue for you.

*Why it was flagged:* Broken 404 on the alternative-sign-in link. Intent is a site fault but the goal is a 2FA reset, so E1 fires.

*Definition used:* Amazon's own devices, apps, or digital services misbehaving.

---

### G179  (labelled `item_problem`, ESCALATE, confidence: medium)

> Every book i order from Amazon seems to get damaged in transit Like. Just wrap the books! A little!!

*Amazon actually replied:* Oh no! So sorry for the trouble! We'd love to help! Have you had the chance to review available options here?: <link>

*Why it was flagged:* Every book arrives damaged. Between a recurring item fault and packaging feedback.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G182  (labelled `item_problem`, ESCALATE, confidence: medium)

> Thanks for nothing , for delivering this unwrapped and in a now damaged box. Good job my son was in bed &amp; you didn't ruin Christmas. #amazonfail <link>

*Amazon actually replied:* Oh no! I'm sorry for the frustration, Rachel. This looks like it was shipped with our Frustration-Free Packaging. You can see more about it and how to get the normal boxes on future orders here: <link>

*Why it was flagged:* Frustration-free packaging exposed a child's Christmas gift; hashtagged #amazonfail.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G185  (labelled `item_problem`, ESCALATE, confidence: medium)

> Our parcels have arrived 3 days late slung over a neighbour's fence and boxes damaged! Disgraceful <link>

*Amazon actually replied:* I'm sorry for the condition of your delivery. Please contact us directly via phone or chat to report this and explore options here: <link>

*Why it was flagged:* Three days late, thrown over a fence, boxes damaged. Damage is the actionable core.

*Definition used:* Item arrived but is wrong, damaged, defective, incomplete or not as described.

---

### G186  (labelled `feedback_other`, auto, confidence: medium)

> Shout out to

*Amazon actually replied:* Thank you, Thank you! We'll be here all week. Try the veal! Or the broccoli. Maybe the tofu? Whichever you prefer, really.

*Why it was flagged:* 'Shout out to' - the @handle was stripped by cleaning, which destroys the meaning of very short messages. Pipeline artifact, kept deliberately.

*Definition used:* Praise, thanks, suggestions, or non-actionable commentary.

---

### G192  (labelled `delivery_delayed`, auto, confidence: low)

> where’s my kindle

*Amazon actually replied:* Hello! Are you referring to a recent order of yours? If so, what does the tracking info state here: <link>

*Why it was flagged:* 'where's my kindle' - three words. Could be an order status or a lost device; Amazon offered both.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.

---

### G193  (labelled `billing_account`, ESCALATE, confidence: low)

> is this legit? <link>

*Amazon actually replied:* Thanks for reaching out to us. We'd recommend to contact the company that you received this from to verify it's legitimacy. I'm sorry for the inconvenience.

*Why it was flagged:* 'Is this legit?' phishing check. Labelled consistently with G029 despite low confidence.

*Definition used:* Charges, subscriptions, payment methods, or account access and security.

---

### G196  (labelled `service_complaint`, ESCALATE, confidence: medium)

> service is bad

*Amazon actually replied:* Certainly not what we expect you to go though. Kindly elaborate on your concern. We would like to help you.

*Why it was flagged:* 'service is bad' - minimal, but it is a service complaint rather than unclassifiable.

*Definition used:* Dissatisfaction with Amazon's service, staff or handling, with no single resolvable order request attached.

---

### G200  (labelled `delivery_delayed`, auto, confidence: medium)

> you guaranteed one day delivery and now my items might take 4 days? I bought extra items just to hit the $35 limit. You guys are snakes.

*Amazon actually replied:* I'm sorry for the wait. What is the delivery date listed within your order confirmation e-mail?

*Why it was flagged:* Hostile tone (snakes) but at open it is a delivery-promise miss. Compensation demand only appears later.

*Definition used:* Ordered item has not arrived yet: late, still in transit, or slower than the promised window.
