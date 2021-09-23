cd /home/step305/face_recognition_server/
sudo echo -e "**********************" | tee -a /home/step305/face_recognition_server/log_door.txt
sudo echo -e "****NEW LOG***********" | tee -a /home/step305/face_recognition_server/log_door.txt
sudo echo -e "**********************" | tee -a /home/step305/face_recognition_server/log_door.txt
sudo python3 doo.py 2>&1 | tee -a /home/step305/face_recognition_server/log_door.txt


