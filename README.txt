a9.mp4 - in root project folder needed to show advertising video

allowed.ogg - in root project folder needed to play sound when access granted

Folder KnownFaces should contain sub-folders like User1...UserN with info about users who have access.

Each Useri sub-folder should contain cardID.txt with card number in ASCII (decimal number of user's access card)
and face_ID.jpg - user's profile photo.

Folder config contains STATIC IP for server and ports which are used for communication.
trained_model.clf was trained as described in https://github.com/ageitgey/face_recognition

Due to some issues with dnn module in cv2 and lack of my knowledge I've chose to have one connection per port
and one sample of server.py for each external client.
TODO - find out how to simplify this

start_servers.py - starts batch of servers each on its own port.

client.py - simple test for client. it uses test.jpg in root folder

doo.py - sample door management script for Jetson Nano controlling the door access

TODO - clean the code, rewrite some stuff

This is project for personal use mainly. And code from it should be considered as for sample use only.
Main purpose is educational - build client-server app using Flask, OpenCV, DLIB (via face_recognition module).

TODO - face liveness detection using ResNet NN.
