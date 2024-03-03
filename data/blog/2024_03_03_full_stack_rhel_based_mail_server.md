# 2024-03-03 - Full stack RHEL-based mail server

## Introduction
Ok so I'm not going to lie, I had no intention of taking the route I am currently taking.
What I mean is that all I wanted to do was rebuild my mail server as my current one predates a lot of my current backbone infrastructure.
I decided to move off of Mail-in-a-Box, which is a fantastic project by the way, as I wanted more flexibility.
Having come across the [ISPmail guide](https://workaround.org/ispmail-bookworm/), I decided to follow this plan while making a few small modifications.

Except in reality they are not small.

I am not using a database for my mail server, but am instead using LDAP.
I am also not building this on Debian, but on Rocky Linux^1.

Because of this, I can't just use the ISPmail guide, but luckily Red Hat docs come in clutch as they have a whole guide each for postfix and dovecot.
These guides together cover a lot of ground for getting to a solid mail server that works, but neither comes close to an all-in-one solution like MAIB in terms of ensuring your mail is almost universally accepted.
In two years of hosting my own mail, I have had only one incident of rejected mail, and that was because my server IP got blocked.
I got that removed within an hour (kudos to the blacklist, they work very quick) and have not had any issues since.
As such, because I am already needing to learn this information to build my own mail server, I'll try to synthesize the guides, my research, and my results here.
I cannot guarantee this will work, as I'm writing this introduction as I'm early in the process.

If you read this and are able to build a working and widely accepted mail server, then please share this guide so the art of being a mail admin doesn't die out.

## Goals
1. Can send emails
2. Can receive emails
3. Emails sent are trusted and widely accepted
    * DKIM
    * DMARC
    * SPF
    * DANE/TLSA
    * MTA-STS
    * DNSSEC
4. DNS is properly configured and maintained
5. Mail server is more than reasonably secure
6. Spam filtering
7. Advanced tools and configurations

## Software
* Rocky Linux
* postfix
    * postfix-mta-sts-resolver
    * postfix-ldap
* dovecot
* rspamd
* redis
* fail2ban
* roundcube

## Installation

1. Setup the rspamd repo

```
$ source /etc/os-release
$ export EL_VERSION=`echo -n $PLATFORM_ID | sed "s/.*el//"`
$ curl https://rspamd.com/rpm-stable/centos-${EL_VERSION}/rspamd.repo > /etc/yum.repos.d/rspamd.repo
$ sed -i 's|gpgkey=http://|gpgkey=https://|' /etc/yum.repos.d/rspamd.repo
```

2. Install packages

```
$ dnf install postfix postfix-ldap postfix-mta-sts-resolver dovecot dovecot-pigeonhole rspamd redis fail2ban ca-certificates swaks
```

3. Install certificates to `/etc/pki/tls/certs/` and certificate keys to `/etc/pki/tls/private/`

## Configuration

### Postfix

1. Set hostname, domain, and origin

```
$ sed -i 's/#myhostname = host.domain.tld/myhostname = HOST.DOMAIN/g' /etc/postfix/main.cf
$ sed -i 's/#mydomain = domain.tld/mydomain = DOMAIN/g' /etc/postfix/main.cf
$ sed -i 's/#myorigin = $mydomain/myorigin = $mydomain/g' /etc/postfix/main.cf
```

2. Configure listening interfaces

```
$ sed -i 's/#inet_interfaces = all/inet_interfaces = all/g' /etc/postfix/main.cf
$ sed -i 's/inet_interfaces = localhost/#inet_interfaces = localhost/g' /etc/postfix/main.cf
```

3. Configure TLS certificates

```
$ sed -i 's|smtpd_tls_cert_file = /etc/pki/tls/certs/postfix.pem|smtpd_tls_cert_file = /etc/pki/tls/certs/CERT|g' /etc/postfix/main.cf
$ sed -i 's|smtpd_tls_key_file = /etc/pki/tls/private/postfix.key|smtpd_tls_key_file = /etc/pki/tls/private/KEY|g' /etc/postfix/main.cf
```

4. Configure security and QoL options

```
$ sed -i 's/#recipient_delimiter = +/recipient_delimiter = +/g' /etc/postfix/main.cf
$ echo 'smtpd_sasl_auth_enable = yes' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_sasl_type = dovecot' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_sasl_path = private/auth' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_sasl_security_options = noanonymous, noplaintext' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_sasl_tls_security_options = noanonymous' | tee -a /etc/postfix/main.cf
$ sed -i 's/smtp_tls_security_level = may/smtp_tls_security_level = dane/g' /etc/postfix/main.cf
$ echo 'smtp_dns_support_level = dnssec' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_tls_auth_only = yes' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_sasl_auth_enable = yes' | tee -a /etc/postfix/main.cf
$ echo 'broken_sasl_auth_clients = yes' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_helo_required = yes' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_sender_restrictions = reject_non_fqdn_sender, reject_unknown_sender_domain, reject_sender_login_mismatch' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_recipient_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_relay_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_data_restrictions = reject_unauth_pipelining' | tee -a /etc/postfix/main.cf
```

See conclusion before setting the following

```
$ echo 'smtpd_client_restrictions = reject_rbl_client zen.spamhaus.org, reject_rhsbl_reverse_client dbl.spamhaus.org, reject_rhsbl_helo dbl.spamhaus.org, reject_rhsbl_sender dbl.spamhaus.org' | tee -a /etc/postfix/main.cf
```

Add this if you implement Dovecot quotas (not covered here)

```
$ echo 'smtpd_end_of_data_restrictions = check_policy_service unix:private/policy' | tee -a /etc/postfix/main.cf
```

5. Configure SMTP-Submission and SMTPS

Set the following options in `/etc/postfix/master.cf`.

```
submission inet n       -       n       -       -       smtpd
  -o syslog_name=postfix/submission
  -o smtpd_tls_security_level=encrypt
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_tls_auth_only=yes
  -o smtpd_milters=inet:127.0.0.1:11332
  -o smtpd_reject_unlisted_recipient=no
#  -o smtpd_client_restrictions=$mua_client_restrictions
#  -o smtpd_helo_restrictions=$mua_helo_restrictions
#  -o smtpd_sender_restrictions=$mua_sender_restrictions
#  -o smtpd_recipient_restrictions=
#  -o smtpd_relay_restrictions=permit_sasl_authenticated,reject
#  -o milter_macro_daemon_name=ORIGINATING
smtps     inet  n       -       n       -       -       smtpd
  -o syslog_name=postfix/smtps
  -o smtpd_tls_wrappermode=yes
  -o smtpd_sasl_auth_enable=yes
  -o smtpd_milters=inet:127.0.0.1:11332
  -o smtpd_reject_unlisted_recipient=no
#  -o smtpd_client_restrictions=$mua_client_restrictions
#  -o smtpd_helo_restrictions=$mua_helo_restrictions
#  -o smtpd_sender_restrictions=$mua_sender_restrictions
#  -o smtpd_recipient_restrictions=
#  -o smtpd_relay_restrictions=permit_sasl_authenticated,reject
#  -o milter_macro_daemon_name=ORIGINATING
```

6. Configure LDAP (see ISPmail guide or the RHEL docs for a database)

```
$ vim /etc/postfix/ldap-aliases.cf
server_host = LDAP_SERVER
search_base = dc=LDAP,dc=DOMAIN
query_filter = (mail=%u@%s)
result_attribute = uid
bind = yes
bind_dn = cn=POSTFIX_LDAP_USER,dc=LDAP,dc=DOMAIN
bind_pw = POSTFIX_LDAP_PASSWD
start_tls = yes
version = 3
$ vim /etc/postfix/ldap-domains.cf
server_host = LDAP_SERVER
search_base = dc=LDAP,dc=DOMAIN
query_filter = (mail=*@%s)
result_attribute = uid
bind = yes
bind_dn = cn=POSTFIX_LDAP_USER,dc=LDAP,dc=DOMAIN
bind_pw = POSTFIX_LDAP_PASSWD
start_tls = yes
version = 3
$ echo 'virtual_mailbox_domains = DOMAIN' | tee -a /etc/postfix/main.cf
$ echo 'virtual_mailbox_maps = ldap:/etc/postfix/ldap-aliases.cf' | tee -a /etc/postfix/main.cf
$ echo 'virtual_alias_maps = ldap:/etc/postfix/ldap-aliases.cf' | tee -a /etc/postfix/main.cf
$ echo 'smtpd_sender_login_maps = ldap:/etc/postfix/ldap-aliases.cf' | tee -a /etc/postfix/main.cf
```

7. Talk to Dovecot

```
$ echo 'virtual_transport = lmtp:unix:/var/run/dovecot/lmtp' | tee -a /etc/postfix/main.cf
```

### Dovecot

1. Configure tls certs

```
$ sed -i 's|ssl_cert = </etc/pki/dovecot/certs/server.example.com.crt|ssl_cert = </etc/pki/dovecot/CERT|g' /etc/dovecot/conf.d/10-ssl.conf
$ sed -i 's|ssl_key = </etc/pki/dovecot/private/server.example.com.key| ssl_key = </etc/pki/dovecot/private/KEY|g' /etc/dovecot/conf.d/10-ssl.conf
$ openssl dhparam -out /etc/dovecot/dh.pem 4096
$ sed -i 's|#ssl_dh = </etc/dovecot/dh.pem|ssl_dh = </etc/dovecot/dh.pem|g' /etc/dovecot/conf.d/10-ssl.conf
$ sed -i 's/#ssl_prefer_server_ciphers = no/ssl_prefer_server_ciphers = yes/g' /etc/dovecot/conf.d/10-ssl.conf
```

2. Configure virtual users

```
$ useradd --home-dir /var/mail/ --shell /usr/sbin/nologin vmail
$ chown vmail:vmail /var/mail/
$ chmod 700 /var/mail/
$ sed -i 's|#mail_location =|mail_location = sdbox:/var/mail/%n/|g' /etc/dovecot/conf.d/10-mail.conf
```

3. Configure LDAP (see ISPmail guide or the RHEL docs for a database)

```
$ sed -i 's/#auth_username_format = %Lu/auth_username_format = %Lu/g' /etc/dovecot/conf.d/10-auth.conf
$ sed -i 's/!include auth-system.conf.ext/#!include auth-system.conf.ext/g' /etc/dovecot/conf.d/10-auth.conf
$ sed -i 's/#!include auth-ldap.conf.ext/!include auth-ldap.conf.ext/g' /etc/dovecot/conf.d/10-auth.conf
$ sed -i '/^userdb {/a \ \ override_fields = uid=vmail gid=vmail home=/var/mail/%n/' auth-ldap.conf.ext
$ vim /etc/dovecot/dovecot-ldap.conf.ext
uris = ldaps://LDAP_SERVER
dn = cn=DOVECOT_LDAP_USER,dc=LDAP,dc=DOMAIN
dnpass = DOVECOT_LDAP_PASSWD
tls_require_cert = hard
auth_bind = yes
auth_bind_user
ldap_version = 3
base = cn=users,cn=accounts,dc=LDAP,dc=DOMAIN
scope = subtree
user_filter = (&(objectClass=posixAccount)(|(uid=%n)(mail=%u)))
pass_filter = (&(objectClass=posixAccount)(|(uid=%n)(mail=%u)))
$ chown root:root /etc/dovecot/dovecot-ldap.conf.ext
$ chmod 600 /etc/dovecot/dovecot-ldap.conf.ext
```

4. Configure Dovecot

```
$ sed -i '/^\s*special_use =/a \ \ \ \ auto = subscribe' /etc/dovecot/conf.d/15-mailboxes.conf
$ sed -i 's/#protocols =.*/protocols = imap lmtp/' /etc/dovecot/dovecot.conf
$ sed -i '/unix_listener lmtp {/a \ \ \ \ group = postfix' /etc/dovecot/conf.d/10-master.conf
$ sed -i '/unix_listener lmtp {/a \ \ \ \ user = postfix' /etc/dovecot/conf.d/10-master.conf
$ sed -i '/unix_listener lmtp {/a \ \ \ \ mode = 0600' /etc/dovecot/conf.d/10-master.conf

$ sed -i '/service auth {/a \ \ unix_listener /var/spool/postfix/private/auth {' /etc/dovecot/conf.d/10-master.conf
$ sed -i '/^\s*unix_listener \/var\/spool\/postfix\/private\/auth {/a \ \ }' /etc/dovecot/conf.d/10-master.conf
$ sed -i '/^\s*unix_listener \/var\/spool\/postfix\/private\/auth {/a \ \ \ \ group = postfix' /etc/dovecot/conf.d/10-master.conf
$ sed -i '/^\s*unix_listener \/var\/spool\/postfix\/private\/auth {/a \ \ \ \ user = postfix' /etc/dovecot/conf.d/10-master.conf
$ sed -i '/^\s*unix_listener \/var\/spool\/postfix\/private\/auth {/a \ \ \ \ mode = 0660' /etc/dovecot/conf.d/10-master.conf
$ sed -i 's/#mail_plugins = $mail_plugins/mail_plugins = $mail_plugins sieve/g' /etc/dovecot/conf.d/20-lmtp.conf
$ sed -i 's/#protocols =/protocols =/' /etc/dovecot/conf.d/20-managesieve.conf
```

### rspamd
* Note, you're probably want to play with the reject value. See the ISPmail guide for more info.
* Note the second, this portion of the guide was pulled pretty much entirely from the ISPmail guide. If you want a much better rspamd guide please go read that, I just don't care to configure this part in as much depth as Postfix and Dovecot.

```
$ vim /etc/rspamd/local.d/actions.conf
reject = 50;
add_header = 6;
greylist = 4;
$ systemctl enable --now postfix dovecot rspamd redis
$ postconf smtpd_milters=inet:127.0.0.1:11332
$ postconf non_smtpd_milters=inet:127.0.0.1:11332
$ postconf milter_mail_macros="i {mail_addr} {client_addr} {client_name} {auth_authen}"
$ echo 'extended_spam_headers = true;' | tee -a /etc/rspamd/override.d/milter_headers.conf
$ mkdir /etc/dovecot/sieve-after
$ sed -i 's|#sieve_after =|sieve_after = /etc/dovecot/sieve-after|' /etc/dovecot/conf.d/90-sieve.conf
$ vim /etc/dovecot/sieve-after/spam-to-folder.sieve
require ["fileinto"];

if header :contains "X-Spam" "Yes" {
 fileinto "Junk";
 stop;
}
$ sievec /etc/dovecot/sieve-after/spam-to-folder.sieve
$ echo 'servers = "127.0.0.1";' | tee -a /etc/rspamd/override.d/redis.conf
$ echo 'autolearn = [-5, 10];' | tee -a /etc/rspamd/override.d/classifier-bayes.conf
$ echo 'users_enabled = true;' | tee -a /etc/rspamd/local.d/classifier-bayes.conf
$ sed -i '/mailbox \(Junk\|Trash\) {/a \ \ \ \ autoexpunge = 30d' /etc/dovecot/conf.d/15-mailboxes.conf
$ sed -i '/protocol imap {/a \ \ mail_plugins = $mail_plugins imap_sieve' /etc/dovecot/conf.d/20-imap.conf
$ sed -i '/plugin {/a \ \ imapsieve_mailbox1_name = Junk' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ imapsieve_mailbox1_causes = COPY' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ imapsieve_mailbox1_before = file:/etc/dovecot/sieve/learn-spam.sieve' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ imapsieve_mailbox2_name = *' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ imapsieve_mailbox2_from = Junk' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ imapsieve_mailbox2_causes = COPY' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ imapsieve_mailbox2_before = file:/etc/dovecot/sieve/learn-ham.sieve' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ sieve_pipe_bin_dir = /etc/dovecot/sieve' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ sieve_global_extensions = +vnd.dovecot.pipe' /etc/dovecot/conf.d/90-sieve.conf
$ sed -i '/plugin {/a \ \ sieve_plugins = sieve_imapsieve sieve_extprograms' /etc/dovecot/conf.d/90-sieve.conf
$ mkdir /etc/dovecot/sieve
$ vim /etc/dovecot/sieve/learn-spam.sieve
require ["vnd.dovecot.pipe", "copy", "imapsieve"];
pipe :copy "rspamd-learn-spam.sh";
$ vim /etc/dovecot/sieve/learn-ham.sieve
require ["vnd.dovecot.pipe", "copy", "imapsieve", "variables"];
if string "${mailbox}" "Trash" {
  stop;
}
pipe :copy "rspamd-learn-ham.sh";
$ systemctl reload-or-restart dovecot
$ sievec /etc/dovecot/sieve/learn-spam.sieve
$ sievec /etc/dovecot/sieve/learn-ham.sieve
$ chmod u=rw,go= /etc/dovecot/sieve/learn-{spam,ham}.{sieve,svbin}
$ chown vmail:vmail /etc/dovecot/sieve/learn-{spam,ham}.{sieve,svbin}
$ vim /etc/dovecot/sieve/rspamd-learn-spam.sh
#!/bin/sh
exec /usr/bin/rspamc learn_spam
$ vim /etc/dovecot/sieve/rspamd-learn-ham.sh
#!/bin/sh
exec /usr/bin/rspamc learn_ham
$ chmod u=rwx,go= /etc/dovecot/sieve/rspamd-learn-{spam,ham}.sh
$ chown vmail:vmail /etc/dovecot/sieve/rspamd-learn-{spam,ham}.sh
$ systemctl reload-or-restart dovecot rspamd
```

### DKIM
* Note, this is also mostly taken from the ISPmail guide

```
$ mkdir /var/lib/rspamd/dkim
$ chown _rspamd:_rspamd /var/lib/rspamd/dkim
$ rspamadm dkim_keygen -d DOMAIN -s mail
```

This will give you a private key that must be kept secret as well as a dns record.
Place the key in `/var/lib/rspamd/dkim/DOMAIN.mail.key` and run the following:

```
$ chown _rspamd /var/lib/rspamd/dkim/*
$ chmod u=r,go= /var/lib/rspamd/dkim/*
```

Add the dns record to any zone or subzone that sends mail (i.e. your domain and any subdomains you use).

```
$ vim /etc/rspamd/local.d/dkim_signing.conf
path = "/var/lib/rspamd/dkim/$domain.$selector.key";
selector_map = "/etc/rspamd/dkim_selectors.map";
$ echo 'DOMAIN mail' | tee -a /etc/rspamd/dkim_selectors.map
$ systemctl restart rspamd
```

### DNS
At this point you almost have a completely working mail server.
We're still missing a few nice to haves (DANE, MTA-STS), but almost everything is working.
Here's the real fun management part of email: DNS.
You should have SPF and DMARC records on every single domain and subdomain you use.

This is a pretty widely covered subject, so I will refer you to the ISPmail guide for this.
My only disagreement with the ISPmail guide is that their method of SPF records is too loose for my preference.
As such, I've included what I do instead which is much easier and automatic.

#### SPF
To add SPF, just add the following TXT record to any domain that isn't sending email:

```
v=spf1 -all
```

And this to all domains that will send email:

```
v=spf1 mx -all
```

## Conclusion
This was a lot of effort.

However, currently I have a brand-spankin-new mail server that I can use to send widely accepted emails.
There are two big missing pieces here, though.
If you build this mail server, you will notice that you need to disable `smtpd_client_restrictions` in Postfix to do anything.
This is because spamhaus is a bit fucky wucky about how you use their stuff so I need to figure that out.

Additionally, I need to figure out MTA-STS and DANE/TLSA.
These are not in here, and neither was Fail2Ban.
As such, there will eventually be a follow up guide once I get to those.
MTA-STS seems easy to setup on the receiving side, but it requires a webserver for sending.
Not ideal, and a lot more work than this has already been.
DANE I just am having a hard time finding really good documentation, but I'll get there.

There was also not a lot of discussion on the LDAP side of things, which took me forever and a half but I got it.
I didn't discuss it very much as this isn't a FreeIPA specific guide (even though it kinda is), but if there's interest I'll write one up.

If you end up setting up an email server off this horribly written guide, or if you just wanna respond or give feedback, please do reach out at developer@groncyber.com.

## Sources
* https://workaround.org/ispmail-bookworm/install-the-software-packages/
* https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/deploying_different_types_of_servers/assembly_mail-transport-agent_deploying-different-types-of-servers
* https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/8/html/deploying_different_types_of_servers/configuring-and-maintaining-a-dovecot-imap-and-pop3-server_deploying-different-types-of-servers
* https://rspamd.com/downloads.html
* https://listman.redhat.com/archives/freeipa-users/2012-January/msg00231.html
* https://www.postfix.org/SMTPD_ACCESS_README.html
* https://docs.rockylinux.org/guides/email/02-basic-email-system/
* Many stackexchange, mailing list, and reddit posts i forgot to copy the URL of

---

## Footnotes
1. Originally this was going to built on top of Fedora Server, but rspamd was only available in the copr repos and I knew that rspamd has first-party support for RHEL-based systems. As this is going to be a critical system for me, I opted to go for the first-party repo and switch to Rocky.
