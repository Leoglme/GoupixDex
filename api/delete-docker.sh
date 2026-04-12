# Delete docker container goupixdex-mariadb, goupixdex-api and goupixdex-phpmyadmin
docker rm -f goupixdex-mariadb goupixdex-api goupixdex-phpmyadmin
# Delete docker image goupixdex-api
docker rmi -f goupixdex-api
# Delete docker volume goupixdex_mariadb_data
docker volume rm goupixdex_mariadb_data