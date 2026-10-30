BEGIN TRANSACTION;
CREATE TABLE authorities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    department TEXT NOT NULL,
    designation TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
INSERT INTO "authorities" VALUES(1,3,'BBMP - Sanitation & Roads','Junior Engineer');
INSERT INTO "authorities" VALUES(2,4,'BWSSB - Water Supply','Assistant Engineer');
INSERT INTO "authorities" VALUES(3,7,'pothole','junior engineering');
CREATE TABLE complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    ai_detected_category TEXT,
    ai_confidence REAL,
    description TEXT NOT NULL,
    photo_path TEXT,
    latitude REAL,
    longitude REAL,
    location_name TEXT,
    priority TEXT NOT NULL DEFAULT 'Medium' CHECK(priority IN ('Low', 'Medium', 'High')),
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'In Progress', 'Resolved')),
    duplicate_of INTEGER,
    duplicate_group TEXT,
    support_count INTEGER DEFAULT 1,
    assigned_to INTEGER,
    resolution_notes TEXT,
    resolved_photo_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (duplicate_of) REFERENCES complaints(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);
INSERT INTO "complaints" VALUES(1,1,'Garbage','Garbage',0.92,'Garbage has been piling up on the roadside for several days and is not being collected.',NULL,12.9698,77.75,'Whitefield Main Road, Bengaluru','Low','Pending',NULL,NULL,1,NULL,NULL,NULL,'2026-09-08 12:03:00','2026-09-08 12:03:00',NULL);
INSERT INTO "complaints" VALUES(2,2,'Water Leakage','Water Leakage',0.88,'There is a continuous water leak from an underground pipe near the footpath.',NULL,12.9758,77.6045,'MG Road, Bengaluru','Medium','In Progress',NULL,NULL,1,4,'Issue verified and work order raised.',NULL,'2026-09-01 12:03:00','2026-09-01 12:03:00',NULL);
INSERT INTO "complaints" VALUES(3,1,'Electricity Issue','Electricity Issue',0.8,'A street light pole has exposed wiring which looks hazardous at night.',NULL,12.9116,77.6389,'HSR Layout Sector 2, Bengaluru','High','Resolved',NULL,NULL,1,3,'Issue fixed and verified on-site.','uploads/resolved_photos/demo_resolved.jpg','2026-09-01 12:03:00','2026-09-01 12:03:00','2026-09-01 12:03:00');
INSERT INTO "complaints" VALUES(4,2,'Pothole','Pothole',0.83,'A large pothole has formed on the main road causing trouble for vehicles.',NULL,12.9719,77.6412,'Indiranagar 100ft Road, Bengaluru','Low','Pending',NULL,NULL,1,NULL,NULL,NULL,'2026-08-29 12:03:00','2026-08-29 12:03:00',NULL);
INSERT INTO "complaints" VALUES(5,1,'Garbage','Garbage',0.75,'Garbage has been piling up on the roadside for several days and is not being collected.',NULL,12.9698,77.75,'Whitefield Main Road, Bengaluru','Medium','In Progress',NULL,NULL,1,3,'Issue verified and work order raised.',NULL,'2026-09-17 12:03:00','2026-09-17 12:03:00',NULL);
INSERT INTO "complaints" VALUES(6,2,'Water Leakage','Water Leakage',0.79,'There is a continuous water leak from an underground pipe near the footpath.',NULL,12.9352,77.6245,'Koramangala 5th Block, Bengaluru','High','Resolved',NULL,NULL,1,4,'Issue fixed and verified on-site.','uploads/resolved_photos/demo_resolved.jpg','2026-09-10 12:03:00','2026-09-10 12:03:00','2026-09-10 12:03:00');
INSERT INTO "complaints" VALUES(7,1,'Electricity Issue','Electricity Issue',0.88,'A street light pole has exposed wiring which looks hazardous at night.',NULL,12.9308,77.5838,'Jayanagar 4th Block, Bengaluru','Low','Pending',NULL,NULL,1,NULL,NULL,NULL,'2026-09-09 12:03:00','2026-09-09 12:03:00',NULL);
INSERT INTO "complaints" VALUES(8,2,'Pothole','Pothole',0.79,'A large pothole has formed on the main road causing trouble for vehicles.',NULL,12.9719,77.6412,'Indiranagar 100ft Road, Bengaluru','Medium','In Progress',NULL,NULL,1,3,'Issue verified and work order raised.',NULL,'2026-09-06 12:03:00','2026-09-06 12:03:00',NULL);
INSERT INTO "complaints" VALUES(9,1,'Garbage','Garbage',0.73,'Garbage has been piling up on the roadside for several days and is not being collected.',NULL,12.9308,77.5838,'Jayanagar 4th Block, Bengaluru','High','Resolved',NULL,NULL,1,3,'Issue fixed and verified on-site.','uploads/resolved_photos/demo_resolved.jpg','2026-08-29 12:03:00','2026-08-29 12:03:00','2026-08-29 12:03:00');
INSERT INTO "complaints" VALUES(10,2,'Water Leakage','Water Leakage',0.78,'There is a continuous water leak from an underground pipe near the footpath.',NULL,12.9719,77.6412,'Indiranagar 100ft Road, Bengaluru','Low','Pending',NULL,NULL,1,NULL,NULL,NULL,'2026-09-04 12:03:00','2026-09-04 12:03:00',NULL);
INSERT INTO "complaints" VALUES(11,1,'Electricity Issue','Electricity Issue',0.9,'A street light pole has exposed wiring which looks hazardous at night.',NULL,12.9719,77.6412,'Indiranagar 100ft Road, Bengaluru','Medium','In Progress',NULL,NULL,1,3,'Issue verified and work order raised.',NULL,'2026-09-16 12:03:00','2026-09-16 12:03:00',NULL);
INSERT INTO "complaints" VALUES(12,2,'Pothole','Pothole',0.65,'A large pothole has formed on the main road causing trouble for vehicles.',NULL,12.9698,77.75,'Whitefield Main Road, Bengaluru','High','Resolved',NULL,NULL,1,3,'Issue fixed and verified on-site.','uploads/resolved_photos/demo_resolved.jpg','2026-09-06 12:03:00','2026-09-06 12:03:00','2026-09-06 12:03:00');
INSERT INTO "complaints" VALUES(13,1,'Garbage','Garbage',0.71,'Garbage has been piling up on the roadside for several days and is not being collected.',NULL,12.9698,77.75,'Whitefield Main Road, Bengaluru','Low','Pending',NULL,NULL,1,NULL,NULL,NULL,'2026-09-04 12:03:00','2026-09-04 12:03:00',NULL);
INSERT INTO "complaints" VALUES(14,2,'Water Leakage','Water Leakage',0.85,'There is a continuous water leak from an underground pipe near the footpath.',NULL,12.9308,77.5838,'Jayanagar 4th Block, Bengaluru','Medium','In Progress',NULL,NULL,1,4,'Issue verified and work order raised.',NULL,'2026-09-08 12:03:00','2026-09-08 12:03:00',NULL);
INSERT INTO "complaints" VALUES(15,1,'Garbage','Garbage',0.64,'gabbage issue','uploads/issue_photos/e039e6cbc0964dc78db33c19b261f288.png',1.300507660119695075e+01,7.756998308245151464e+01,'Detected via GPS','Medium','Pending',NULL,NULL,1,NULL,NULL,NULL,'2026-09-17 07:40:22','2026-09-17 07:40:22',NULL);
INSERT INTO "complaints" VALUES(16,5,'Pothole','Garbage',0.66,'In our area iam getting a pathole issues please came nd solve the problem','uploads/issue_photos/415fda6562814b8489f62c312385b950.png',1.300506554640629097e+01,7.757005498387756859e+01,'Detected via GPS','Medium','Pending',NULL,NULL,1,NULL,NULL,NULL,'2026-09-17 07:48:46','2026-09-17 07:48:46',NULL);
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    complaint_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (complaint_id) REFERENCES complaints(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
INSERT INTO "feedback" VALUES(1,3,1,4,'Thanks for resolving this quickly.','2026-09-18 06:33:00');
INSERT INTO "feedback" VALUES(2,6,2,3,'Thanks for resolving this quickly.','2026-09-18 06:33:00');
INSERT INTO "feedback" VALUES(3,9,1,3,'Thanks for resolving this quickly.','2026-09-18 06:33:00');
INSERT INTO "feedback" VALUES(4,12,2,4,'Thanks for resolving this quickly.','2026-09-18 06:33:00');
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    complaint_id INTEGER,
    message TEXT NOT NULL,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (complaint_id) REFERENCES complaints(id)
);
INSERT INTO "notifications" VALUES(1,3,1,'New civic complaint reported: Garbage - Low Priority (Whitefield Main Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(2,2,2,'Your complaint (Water Leakage) status: In Progress.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(3,4,2,'New civic complaint reported: Water Leakage - Medium Priority (MG Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(4,1,3,'Your complaint (Electricity Issue) status: Resolved.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(5,3,3,'New civic complaint reported: Electricity Issue - High Priority (HSR Layout Sector 2, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(6,3,4,'New civic complaint reported: Pothole - Low Priority (Indiranagar 100ft Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(7,1,5,'Your complaint (Garbage) status: In Progress.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(8,3,5,'New civic complaint reported: Garbage - Medium Priority (Whitefield Main Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(9,2,6,'Your complaint (Water Leakage) status: Resolved.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(10,4,6,'New civic complaint reported: Water Leakage - High Priority (Koramangala 5th Block, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(11,3,7,'New civic complaint reported: Electricity Issue - Low Priority (Jayanagar 4th Block, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(12,2,8,'Your complaint (Pothole) status: In Progress.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(13,3,8,'New civic complaint reported: Pothole - Medium Priority (Indiranagar 100ft Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(14,1,9,'Your complaint (Garbage) status: Resolved.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(15,3,9,'New civic complaint reported: Garbage - High Priority (Jayanagar 4th Block, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(16,4,10,'New civic complaint reported: Water Leakage - Low Priority (Indiranagar 100ft Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(17,1,11,'Your complaint (Electricity Issue) status: In Progress.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(18,3,11,'New civic complaint reported: Electricity Issue - Medium Priority (Indiranagar 100ft Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(19,2,12,'Your complaint (Pothole) status: Resolved.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(20,3,12,'New civic complaint reported: Pothole - High Priority (Whitefield Main Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(21,3,13,'New civic complaint reported: Garbage - Low Priority (Whitefield Main Road, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(22,2,14,'Your complaint (Water Leakage) status: In Progress.',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(23,4,14,'New civic complaint reported: Water Leakage - Medium Priority (Jayanagar 4th Block, Bengaluru)',0,'2026-09-18 06:33:00');
INSERT INTO "notifications" VALUES(24,3,15,'New civic complaint reported: Garbage - Medium Priority (Detected via GPS)',0,'2026-09-17 07:40:22');
INSERT INTO "notifications" VALUES(25,4,15,'New civic complaint reported: Garbage - Medium Priority (Detected via GPS)',0,'2026-09-17 07:40:22');
INSERT INTO "notifications" VALUES(26,3,16,'New civic complaint reported: Pothole - Medium Priority (Detected via GPS)',0,'2026-09-17 07:48:46');
INSERT INTO "notifications" VALUES(27,4,16,'New civic complaint reported: Pothole - Medium Priority (Detected via GPS)',0,'2026-09-17 07:48:46');
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('citizen', 'authority', 'admin')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO "users" VALUES(1,'Anita Rao','citizen@example.com','9900000001','scrypt:32768:8:1$sFjMy0XUfp89LXkG$1ca51990e5b2e2c225ad547865036684304db52e7640941b8cdef529fb10311f3d5530dfa500c97ec296ee2a8807eeb79b423d9b6ae07f1d39c87deb1bb07000','citizen','2026-09-18 06:33:00');
INSERT INTO "users" VALUES(2,'Ravi Kumar','citizen2@example.com','9900000002','scrypt:32768:8:1$3qJMEklhN6QMIOiR$7feae2f5defa12d60ad0c035a58259a69d180dbff1806a9bab23f829d3073df92d1a9b78291eef73f4429ae2f9968ffaddfc79cb4dc6bf8b218f6f96a433ffd6','citizen','2026-09-18 06:33:00');
INSERT INTO "users" VALUES(3,'Suresh Patil','admin@example.com','9900000003','scrypt:32768:8:1$n3mal2BG9jValmDm$611df8ff0b48f15cfd3223fd3c25e942083bf13f2edb49e8f2ebdfce860537780883ae09ca21eeafa87f619bd4ca2164932a1fb107886c167f3c14a4ef4dc9a7','authority','2026-09-18 06:33:00');
INSERT INTO "users" VALUES(4,'Deepa Shetty','water@example.com','9900000004','scrypt:32768:8:1$GSphvMh4il9CCSWv$6c8158b533db3d105e301f1bafc7567b87f8068128ff0fa84c484eec2e56fa69ab404c6ea1b9d21f0b41981035c2dfe9293f28a6148b6e3595182bc5ecfc62ff','authority','2026-09-18 06:33:00');
INSERT INTO "users" VALUES(5,'Vidhya.M','vidhya123@gmail.com','987654321','scrypt:32768:8:1$AxAxDRlsF51OCa3b$12d504453753ab31bf6b1db2070d2e1e8ba3d9f79b805493937664df14898477bbaf9d1f8c842bd56c0569453d4b2c4d016b9546da023f3429ff2bad29ac14df','citizen','2026-09-17 07:46:54');
INSERT INTO "users" VALUES(6,'Admin User','admin@test.com','9999999999','scrypt:32768:8:1$sLkzP8ub4oA7ce2h$396be2235fce6bddded01a09344d42aba30ca561d9768bdd7d8151162bd13debff68062e86deb3fa22042a7b19230658aaee93874f0dba639491ff15791d3f3a','admin','2026-09-18 07:38:32');
INSERT INTO "users" VALUES(7,'mohan','mohan111@gmail.com','987654321','scrypt:32768:8:1$OAC04VJaSMBTTcHr$6a69d7b9f94e8365cf0ac700ebb5df95a987256e6f294d8f6163376c0a604b8fe3fb73660b35aaa8aa11b4eff4d218cd955c54bcf533c08d8ebc1d0679b0064d','authority','2026-09-18 07:41:09');
CREATE INDEX idx_complaints_user ON complaints(user_id);
CREATE INDEX idx_complaints_status ON complaints(status);
CREATE INDEX idx_complaints_category ON complaints(category);
CREATE INDEX idx_notifications_user ON notifications(user_id);
CREATE INDEX idx_feedback_complaint ON feedback(complaint_id);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('users',7);
INSERT INTO "sqlite_sequence" VALUES('authorities',3);
INSERT INTO "sqlite_sequence" VALUES('complaints',16);
INSERT INTO "sqlite_sequence" VALUES('notifications',27);
INSERT INTO "sqlite_sequence" VALUES('feedback',4);
INSERT INTO "sqlite_sequence" VALUES('users',5);
INSERT INTO "sqlite_sequence" VALUES('authorities',2);
INSERT INTO "sqlite_sequence" VALUES('complaints',16);
INSERT INTO "sqlite_sequence" VALUES('notifications',27);
INSERT INTO "sqlite_sequence" VALUES('feedback',2);
COMMIT;
