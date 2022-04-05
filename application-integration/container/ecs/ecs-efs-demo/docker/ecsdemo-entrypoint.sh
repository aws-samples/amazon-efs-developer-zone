#!/bin/bash

function set_siteurl() {
  sleep 3
  URL=$(curl -s ifconfig.co)
  echo -e "define( 'WP_SITEURL', 'http://$URL' );" >> /var/www/html/wp-config.php
}

set_siteurl&
/usr/local/bin/docker-entrypoint.sh $@
