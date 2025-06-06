Setting up dokku
---

The outreachy-website server uses dokku to host the Django/Wagtail server.
When in doubt, reference the dokku documentation for getting dokku set up:
 - [Dokku installation instructions](http://dokku.viewdocs.io/dokku/getting-started/installation/)
 - [Dokku app deployment instructions](http://dokku.viewdocs.io/dokku/deployment/application-deployment/)

On the server, you'll need to setup the dokku postgres plugin:
```
$ sudo dokku plugin:install https://github.com/dokku/dokku-postgres.git
```

For the remaining steps, you can either run dokku commands on the server, or run them on your local computer using ssh. All commands that need to run on the server will start with:
```
$ ssh dokku@$DOMAIN
```
(where you need to replace "$DOMAIN" with the name of the server you're using that has dokku installed) but if you're running them directly on the server then you can replace that with
```
$ dokku
```

If you need help with any dokku commands at any time, you can ask for the documentation with a command like this:
```
$ ssh dokku@$DOMAIN config:help
```

The next step is to ask Dokku for space to deploy a new app, which we'll call $APP in this document:
```
$ ssh dokku@$DOMAIN apps:create $APP
```

Whatever name you use for $APP, if it doesn't have any periods in it (like "outreachy-test" or "www"), Dokku will append the domain name you've configured as its default. For example, on the live site, we use "www", and let Dokku append ".outreachy.org" to that.

Next, you can either create a new database, or clone an existing database:

 - Create an empty PostgreSQL database to store all the site data:
   ```
    $ ssh dokku@$DOMAIN postgres:create $APP-database
    ```
 - With the outreachy.org website, we have the production database and the test database. You can clone the production database into a new test database with the command:
   ```
   $ ssh dokku@$DOMAIN postgres:clone $PRODUCTION-database $TEST-database
   ```

Now that we have a database, we can link the www Django app to the www-database postgres database:
```
$ ssh dokku@$DOMAIN postgres:link $APP-database $APP
```

If you're curious, you can ask Dokku to show you the configuration for the database, including the internal environment variable which is a URL containing a unique password to access the database:
```
$ ssh dokku@$DOMAIN config $APP
```

Images
------

Each time we push to dokku, or change the configuration, the docker container that hosts the Outreachy website is destroyed and re-deployed.
By default, any images we've uploaded through wagtail or django will be destroyed as well.
There are two ways to work around this: setting up cloud storage on Rackspace, or setting up persistent storage in dokku, which will simply use the server's disk space.
We expect that users who can upload images will be either community coordinators, mentors, or interns.
In the future, when we migrate the application system over to wagtail and django, we may also have applicants uploading files like resumes (which are optional).
One threat model to keep in mind is a group of malicious people trying to flood the application system with applications and large files.
Putting a limit on the file size might help, but won't stop such an attack.
For now, we'll go with [dokku persistent storage](http://dokku.viewdocs.io/dokku/advanced-usage/persistent-storage/) with the help of a package called dj-static.

Dokku will create a new directory /var/lib/dokku/data/storage, and we create a subdirectory for the www dokku app (our wagtail/django app) on the server, which bind mounts django's /app/media (default storage in the container) to /var/lib/dokku/data/storage/$APP:
```
$ ssh dokku@$DOMAIN storage:mount $APP /var/lib/dokku/data/storage/$APP:/app/media
```
(Note: if you are running a test app, and you want that app to have access to the production app's media, you can replace the second $APP with your production app's name. Only do this if you trust your test app users to not delete all your media!)

Configure environment variables
-------------------------------

Clone the git repo:
```
$ git clone git@github.com:outreachy/website.git outreachy
$ cd outreachy
```

In this repo, we've told Django to get certain settings from environment variables. You can find all the environment variables we rely on in `outreachyhome/settings/production.py`. In order to tell Django to use that file, we also have to set `DJANGO_SETTINGS_MODULE`.

Most importantly, for a public-facing deployment, we need a unique random value for `SECRET_KEY`. You can generate it any way you want but we use `pwgen`.
```
$ ssh dokku@$DOMAIN config:set $APP DJANGO_SETTINGS_MODULE=outreachyhome.settings.production SECRET_KEY="`pwgen -sy 50 1`"
```

If you see an error message like `xargs: unmatched double quote; by default quotes are special to xargs unless you use the -0 option`, it means pwgen came up with a password with a quote or single quote in it. You'll need to set the SECRET_KEY again, because Dokku doesn't shell-escape these variables.

You also need to tell Django which hostname it's being deployed at or it will return `400 Bad Request` without telling you why (although we've configured it to at least log the error in `dokku logs $APP`). That's probably something like this:
```
$ ssh dokku@$DOMAIN config:set $APP ALLOWED_HOSTS=$APP.$DOMAIN
```

The Outreachy website sends outgoing mail (for example from the contact form), so you'll need a mailserver that can handle SMTP. You can skip this if you want, but anything trying to send email will fail. You can also come back to this step and do it later.
Set up Django to send email through your mail server by filling in these variables with your own account information:
```
$ ssh dokku@$DOMAIN config:set $APP EMAIL_HOST=mailhost EMAIL_PORT=port EMAIL_USE_SSL=True EMAIL_HOST_USER=emailusername EMAIL_HOST_PASSWORD=password
```

In its default configuration, the `gunicorn` web server can only handle one request at a time. Ideally all requests would respond quickly and this wouldn't matter, but in practice it does. The documentation recommends that however many CPU cores you have, you should run 2-4 times as many worker processes. So if you have 8 cores and want to run twice as many worker processes, set this:
```
$ ssh dokku@$DOMAIN config:set $APP WEB_CONCURRENCY=16
```

Deploy
------

Now, finally! we can deploy the app on the server, following the dokku "Deploy the app" section:

On the local box, git commit, and add the dokku as a remote:
```
$ git remote add dokku dokku@$DOMAIN:$APP
$ git push dokku HEAD:master
```
(Note: dokku will only pull from the master branch on the git repo when it's deploying an app.)

Apply all the Django migrations we've set up:
```
$ ssh dokku@$DOMAIN run $APP python manage.py migrate
```

After the first deploy, the Node and Python packages are cached, but sometimes this cache goes bad. In that case you can purge the cache before deploying again:

```
$ ssh dokku@$DOMAIN repo:purge-cache $APP
```

Create Django Superuser
=======================

If you created a new database (not cloned an existing database) we need to follow the Django directions to create a superuser. If you are running this from your local computer, for this ssh command you need to run `ssh -t` or you won't be able to type answers to the questions this command prompts you with.
```
$ ssh -t dokku@$DOMAIN run $APP python manage.py createsuperuser
```

SSL certificate
---------------

Follow [the dokku-letsencrypt plugin instructions](https://github.com/dokku/dokku-letsencrypt) to add a Let's encrypt SSL certificate.

Add a cron job to auto-renew the certificate:
```
$ ssh dokku@$DOMAIN letsencrypt:cron-job --add
```

Updating dokku plugins
----------------------

Dokku has two types of plugins: core plugins and external plugins. Core plugins are updated when the base version of dokku is updated.

Upgrading the base dokku version doesn't automatically upgrade external plugins. The two external plugins we have are git-rev and letsencrypt.

Read [dokku plugin management](https://dokku.com/docs/advanced-usage/plugin-management/)

```
dokku plugin:list
```

Updating dokku lets-encrypt plug-in
---

You'll need to periodically update the dokku let's encypt plug in, following the instructions in the [README](https://github.com/dokku/dokku-letsencrypt#upgrading-from-previous-versions). You need to actually ssh into the machine; you can't run this command remotely:
```
dokku plugin:update letsencrypt [git tag]
```

You'll need to specify which tagged version ("commitish") to update to. Check the GitHub repo [tags](https://github.com/dokku/dokku-letsencrypt/tags).

Updating the letsencrypt SSL certificates
---

First, copy the current certificates to a backup directory:

```
cp -a /home/dokku/www/letsencrypt/ letsencrypt-dokku-backup-2022-06-27
```

Then run the command to renew the www subdomain certificates:

```
dokku letsencrypt:auto-renew www
```

If you need to run debug commands in the container, you can enter the container:

```
dokku enter www
```

When debugging the letsencrypt dokku plugin, there are a couple of resources you might look at:

 - [Lets Encrypt forum](https://community.letsencrypt.org)
 - [Dokku plugin documentation](https://dokku.com/docs/advanced-usage/plugin-management/)
 - [Dokku letsencrypt plugin documentation](https://github.com/dokku/dokku-letsencrypt)
 - [Getting a shell with the enter container dokku command](https://dokku.com/docs/processes/entering-containers/)
 - [Setting dokku configuration variables](https://dokku.com/docs/configuration/environment-variables/)
 - [Dokku redirect plugin](https://github.com/dokku/dokku-redirect/) - this ensures that the letsencrypt verification information is served on both www.outreachy.org and outreachy.org


File upload size limits
-----------------------

To avoid denial of service attacks, it's important that the server reject attempts to upload files that are excessively large. In Dokku, the first line of defense against this attack is the nginx [`client_max_body_size`](https://nginx.org/en/docs/http/ngx_http_core_module.html#client_max_body_size) setting, which defaults to 1MB. But we allow people to upload their own profile photos and they often try to use pictures which exceed this limit, then get an inscrutable "413 Request Entity Too Large" error message.

There are two ways to address the UX issues this causes: either increase the size limit, or improve the error message. You can do both at the same time if you want.

Both ways require additional nginx configuration. Dokku documentation first covers how to replace their default nginx configuration wholesale, but I don't recommend that if you can avoid it, so instead, create a config snippet in `/home/dokku/$APP/nginx.conf.d/` as documented under ["Customizing via configuration files included by the default templates"](http://dokku.viewdocs.io/dokku/configuration/nginx/#customizing-via-configuration-files-included-by-the-default-tem).

To change the limit, add a line like this to the new config file:

```
client_max_body_size 5m;
```

To change the error page, add an [`error_page`](https://nginx.org/en/docs/http/ngx_http_core_module.html#error_page) setting like this:

```
error_page 413 /request-too-large
```

The `/request-too-large` path can be any path you want that's configured in Django. Then when nginx would serve up its own 413 response, it instead pretends like the visitor requested `https://www.outreachy.org/request-too-large` and returns whatever response Django generates for that URL. So you can reuse existing Django templates to make sure the error page matches the style of the rest of the site.

Updating the test database
--------------------------

Periodically, you'll want to import the live database to the test site, in order to try a new migration or test new views code. You could export the database as a backup, but that won't work if the schema used on the test site differs from the live site. Instead, we need to clone the live site's database and do a little dance to link it into the test site.

First, clone the live database (www-database):
```
ssh dokku@outreachy.org postgres:clone www-database test-database-updated-2018-02-13
```

Next, link the cloned database to the dokku test container:
```
ssh dokku@outreachy.org postgres:link test-database-updated-2018-02-13 test
```

We promote the cloned database to be used by the test container:
```
ssh dokku@outreachy.org postgres:promote test-database-updated-2018-02-13 test
```

Figure out what the name of the old database linked to the test app is with these commands:
```
ssh dokku@outreachy.org postgres:list
ssh dokku@outreachy.org postgres:app-links test
```

Then we unlink the older database (use whatever was the old name):
```
ssh dokku@outreachy.org postgres:unlink test-database-updated-old test
```

Then you can `git push` to the test site, migrate, and test any updated views.

Finally, we can destroy the older database (use whatever was the old name):
```
ssh dokku@outreachy.org postgres:destroy test-database-updated-old
```

Debugging
---

You can turn on dokku log verbosity by running:

```
ssh dokku@outreachy.org trace:on
```

Turn it off by running:

```
ssh dokku@outreachy.org trace:off
```

Sometimes postgres linking fails? If you have unlinked your old database and you get this error when you link in the new one `Unable to use default or generated URL alias`, then run the following command:

```
ssh dokku@outreachy.org config:unset --no-restart test DATABASE_URL DOKKU_POSTGRES_YELLOW_URL
```

Debugging Slow Database Queries
---

If the site is being slow and you don't know why, a good first guess is that some database query is the culprit, but which one is it? If `DEBUG=True` then the Django Debug Toolbar is very helpful, but often performance problems only show up on the live site, where debugging must be turned off for security reasons.

So instead you can tell Postgres to log queries that take longer than a certain amount of time.

```
ssh -t dokku@outreachy.org postgres:connect www-database
```

```
ALTER SYSTEM SET log_min_duration_statement = 1000;
SELECT pg_reload_conf();
```

These log messages are supposed to be accessible like so:

```
ssh dokku@outreachy.org postgres:logs www-database -t
```

However that didn't work for reasons I don't understand, so I had to run this as root on the host server instead:

```
docker logs --tail 50 dokku.postgres.www-database
```

When you're done, don't forget to turn the logging back off:

```
ALTER SYSTEM RESET log_min_duration_statement;
```

Backing Up the Database
---

`ssh dokku@outreachy.org postgres:export www-database > outreachy-website-database-backup.sql`

This will give you a raw SQL database that you can use to reinstall the website if needed.


Resetting dokku
---------------

Sometimes after you do a server update, dokku is not serving the website. You can restart dokku by running this command:

```
ssh -t dokku@outreachy.org ps:restart www
```

# Stopping dokku containers

Very rarely, it makes sense to stop dokku containers completely. This is usually because you want to debug one container's behavior alone (e.g. stopping the test website dokku containers).

```
ssh -t dokku@outreachy.org ps:stop test
```

Then run `docker ps` to make sure dokku was actually able to shutdown the containers. If the Outreachy web server is out of memory, it may not be able to. In that case, you should restart the server and quickly shut down the dokku containers. You may have to research how to turn off the automatic restart of docker containers (there's an option to dokku for that).

# Debugging memory issues

Commands to explore what's happening:

See how much memory is free:
```
free -h
```

To see which processes are taking the most memory, run this command, hit F6, and use the arrow keys to select sort by memory usage, and hit enter:
```
htop
```

You may want to see if lowering the number of gunicorn processes (the python server HTTP) helps (but don't forget to set it back to 16 after you're done debugging!):

```
dokku config:set test WEB_CONCURRENCY=2
dokku config:set www WEB_CONCURRENCY=4
```

If lowering the concurrency still doesn't help, move onto the debugging dokku and docker section to see if there are old unused docker containers taking up memory.

# Debugging dokku and docker

Dokku manages docker containers.

To see which docker containers are currently running, run this on the server:

```
docker ps
```

There should be 4 docker containers running. Two will be for each of the postgres containers for both the www and test databases. Two will be for the test and www webserver containers. Example output:

```
CONTAINER ID        IMAGE               COMMAND                  CREATED             STATUS              PORTS               NAMES
ID                  IMAGE ID            "/start web"             27 hours ago        Up 9 minutes                            test.web.1
ID                  dokku/www:latest    "/start web"             13 days ago         Up 9 minutes                            www.web.1
ID                  postgres:9.6.1      "/docker-entrypoint.…"   6 months ago        Up 9 minutes        5432/tcp            dokku.postgres.test-database-updated-DATE
ID                  postgres:9.6.1      "/docker-entrypoint.…"   6 years ago         Up 9 minutes        5432/tcp            dokku.postgres.www-database
```

The first row is the container ID of the docker container.

You can see what containers dokku expects to be running with this command:

```
# dokku ps:report
=====> test ps information
       Deployed:                      true
       Processes:                     1
       Ps can scale:                  true
       Ps computed procfile path:     Procfile
       Ps global procfile path:       Procfile
       Ps procfile path:
       Ps restart policy:             on-failure:10
       Restore:                       false
       Running:                       true
       Status web 1:                  running (CID: ID)
=====> www ps information
       Deployed:                      true
       Processes:                     1
       Ps can scale:                  true
       Ps computed procfile path:     Procfile
       Ps global procfile path:       Procfile
       Ps procfile path:
       Ps restart policy:             on-failure:10
       Restore:                       false
       Running:                       true
       Status web 1:                  running (CID: ID)
```

Match the two IDs that are running to the container IDs above. Any docker container ID that is not listed by dokku is not needed and can be shut down.

Next, see what postgres docker containers dokku expects:

```
# dokku postgres:list
NAME                              VERSION         STATUS   EXPOSED PORTS  LINKS
test-database-updated-2022-11-21  postgres:9.6.1  running  -              -
test-database-updated-2022-12-26  postgres:9.6.1  running  -              -
test-database-updated-2023-05-31  postgres:9.6.1  running  -              test
www-database                      postgres:9.6.1  running  -              www
www-database-backup-2022-12-26    postgres:9.6.1  running  -              -
```

The postgres URL for the docker container should match the database name that is linked to either test or www. In the example above, www-database and test-database-updated-2023-05-31 are linked to the two web apps.

Any postgres database not currently linked to the websites should be destroyed.

Any docker containers that have a postgres URL that doesn't match a currently linked database can be shut down.

If you see a old docker container, you can shut it down:

```
docker stop CONTAINERID
```

# Debugging high amounts of web traffic

nginx is a generic web server, proxy, caching, and load balancing software. nginx is in charge of handing off HTTP requests to the python web server for the Outreachy Django website. That Python web server is called gunicorn.

nginx logs are a great place to go to understand which web pages are being accessed, and by whom. Run the following command on the web server to see some examples:

```
# less /var/log/nginx/www-access.log
```

Examples:
```
97.xxx.xxx.xxx - - [04/Dec/2023:17:04:30 +0000] "HEAD / HTTP/2.0" 502 122 "https://www.outreachy.org/" "Mozilla/5.0 (X11; Linux x86_64; rv:xxx.0) Gecko/DATE Firefox/xxx.0"
128.xxx.xxx.xxx - - [04/Dec/2023:21:13:11 +0000] "GET /sponsor HTTP/1.1" 301 0 "https://outreachy.org/sponsor" "Not A;Brand\x22;v=\x2299\x22, \x22Chromium\x22;v=\x2290\x22, \x22Google Chrome\x22;v=\x2290"
```

There are a few parts to these logs:
 1. IP address of the person who requested the website page. Note that this could be the exit node of a VPN or Tor onion server, not the actual person's local IP address.
 2. The time (based on the web server's internal clock) that someone accessed that page.
 3. The HTTP request sent, the HTTP status returned, and the number of bytes in the HTTP body that was returned.
 4. The website URL they were interacting with.
 5. The browser string. All browser strings typically start with Mozilla/5.0, and then go into further detail about the operating system and actual browser name and version string. If you see an odd browser string like the "Not A;Brand..." above, it's like to be a bot crawling the website.

You can run a command to get an idea of how many times an IP address has accessed the website:

```
cut -d " " -f 1 /var/log/nginx/www-access.log | sort | uniq -c | sort -rn | less
```

The number of times is relative to how far back the www-access.log file goes. If you need to access more data, you might need to run zcat to unzip the gzipped log files and concatenate them together.

In general, around 500 or 600 accesses per day is pretty standard for an Outreachy organizer.

Sending mass emails
-------------------

When you need to send a mass email manually, you can do so through the dokku interface to the Django shell. It's useful to run the commands under the test database, because it will simply print out the messages, rather than sending them. Make sure to migrate the test database to an updated version from the live site, using the instructions above.

Then, ssh into the test server shell, and run the commands you want. In this example, we'll simulate clicking the "Contributor Deadline Email" button on the staff dashboard:

```
$ ssh -t dokku@www.outreachy.org run www env --unset=SENTRY_DSN python manage.py shell
Python 3.6.3 (default, Nov 14 2017, 17:29:48) 
[GCC 5.4.0 20160609] on linux
Type "help", "copyright", "credits" or "license" for more information.
(InteractiveConsole)
>>> from django.test import Client
>>> from django.contrib.auth.models import User
>>> c = Client(HTTP_HOST='www.outreachy.org') # set this to the domain you expect to be on
>>> c.force_login(User.objects.filter(is_staff=True, comrade__isnull=False)[0])
>>> c.post('/email/contributor-deadline-reminder/', secure=True)
```

If this is run on the test server, you should see lots of email bodies get printed; the live server will send them to their intended recipients, instead. Either way, if it worked, you should eventually see:

```
<HttpResponseRedirect status_code=302, "text/html; charset=utf-8", url="/dashboard/">
```

Sending mass emails manually
----------------------------

To send a message to an Outreachy intern, and include their mentors (note this means the email will be sent with interns and mentors in the 'To' email header, but there's no way with Django to set the 'Cc' header):

```
$ ssh -t dokku@www.outreachy.org run www env --unset=SENTRY_DSN python manage.py shell
>>> from home import models
>>> from django.core.mail import send_mail
>>> current_round = models.RoundPage.objects.latest('internstarts')
>>> interns = current_round.get_approved_intern_selections()
>>> request = { 'scheme': 'https', 'get_host': 'www.outreachy.org' }
>>> subject = '[Outreachy] Important information'
>>> body = '''Hi {},
... 
... This is a multiline message.
... 
... This is the second line.
... 
... This is the third line.
... 
... This is the final line.
... 
... Outreachy Organizers'''
>>> for i in interns:
...     emails = [ i.applicant.applicant.email_address() ]
...     message = body.format(i.applicant.applicant.public_name.split()[0]).strip()
...     for m in i.mentors.all():
...             emails.append(m.mentor.email_address())
...     send_mail(message=message.strip(), subject=subject.strip(), recipient_list=emails, from_email=models.Address("Outreachy Organizers", "organizers", "outreachy.org"))
... 
```

# Emailing applicants

If you need to email applicants who filled out a final application:

```
>>> from home import models
>>> from django.core.mail import send_mail
>>> body = '''Hi {},
... 
... This is a multiline message.
... 
... This is the second line.
... 
... Outreachy Organizer'''
>>> current_round = models.RoundPage.objects.latest('internstarts')
>>> comrades = models.Comrade.objects.filter(applicantapproval__application_round=current_round, applicantapproval__finalapplication__isnull=False, applicantapproval__approval_status=models.ApprovalStatus.APPROVED).distinct()
>>> for c in comrades:
...     message = body.format(c.public_name.split()[0]).strip()
...     send_mail(message=message, subject=subject.strip(), recipient_list=[c.email_address()], from_email=models.Address("Outreachy Organizers", "organizers", "outreachy.org"))
```

# Marking interns as paid

If all interns can be paid:

```
>>> from home.models import *
current_round = RoundPage.objects.get(interstarts='YYYY-MM-DD')
>>> interns = current_round.get_in_good_standing_intern_selections()
>>> for i in interns:
...     try:
...             if i.finalmentorfeedback.payment_approved and not i.finalmentorfeedback.organizer_payment_approved:
...                     i.finalmentorfeedback.organizer_payment_approved = True
...                     i.finalmentorfeedback.save()
...     except FinalMentorFeedback.DoesNotExist:
...             pass
... 
>>> 
```

If you have a list of interns that have their payment authorized, but not all interns should be paid:

```
>>> emails = [ ... ]
>>> from home import models
>>> feedback = models.Feedback2FromMentor.objects.filter(intern_selection__applicant__applicant__account__email__in=emails).exclude(organizer_payment_approved=False).filter(payment_approved=True)
>>> for f in feedback:
...     f.organizer_payment_approved = True
...     f.save()
...
>>>
```

You can use the following regular expression command in vim to turn a list of interns in format "Name <email> # community" into a list of emails:

```
%s/^.*<\(.*\)>.*/"\1",/
```
