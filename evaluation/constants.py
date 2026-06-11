"""
Evaluation Constants - Department Configurations
"""

CS_CLERK_RESULT_TRADES = [
    'CLK',
    'CLERK',
    'Clerk',
    'SVY_TOPO',
    'DTMN_TECH',
    'TRADESMAN',
    'Tradesman',
    'TRADESMAN_TRADE',
    'AFV',
]

CS_ASSESSMENT_EVENTS = [
    'Initiative & Drive (09)',
    'OP Orientation (15)',
    'Team Spirit (10)',
    'OP Dply & Uses of Trade Eqpt (08)',
    'Adaptibility (10)',
    'Dedication to Org (07)',
    'Spl Achievement (07)',
    'Motivation and Courage (08)',
    'Dependability (12)',
]

CS_ASSESSMENT_MAX_MARKS = {
    'Initiative & Drive (09)': 9,
    'OP Orientation (15)': 15,
    'Team Spirit (10)': 10,
    'OP Dply & Uses of Trade Eqpt (08)': 8,
    'Adaptibility (10)': 10,
    'Dedication to Org (07)': 7,
    'Spl Achievement (07)': 7,
    'Motivation and Courage (08)': 8,
    'Dependability (12)': 12,
}

DEPT_CONFIG = {
    'A': {
        'name': 'Battalion',
        'sub_departments': ['1TB', '2TB', 'STB'],
        'total_marks': 500,
        'categories': [
            ('physical', 'Physical Efficiency'),
            ('weapon', 'Weapon Training'),
            ('field', 'Field Craft'),
            ('assessment', 'Assessment'),
        ],
        'test_types': [
            ('PPT', 'PPT'),
            ('BPET', 'BPET'),
            ('Firing', 'Firing'),
            ('DST', 'DST'),
            ('MR_III', 'MR-III'),
            ('BFC', 'BFC Test'),
            ('PDP', 'PDP Test'),
            ('FC_All', 'FC Practical, FC Online & Camp Trg'),
        ],


        
        'test_to_category': {
            'PPT': 'physical',
            'BPET': 'physical',
            'Firing': 'weapon',
            'DST': 'assessment',
            'MR_III': 'assessment',
            'BFC': 'assessment',
            'PDP': 'assessment',
            'FC_All': 'field',
        },
        'test_config': {
            'PPT': {
                'columns': ['1st Attempt', '2nd Attempt', '3rd Attempt', 'Event Wise Best'],
                'sub_events': ['2.4 KM Run', '100M Sprint', 'Chin Up', 'Sit Up', 'Toe Touch', '5 Mtr Shuttle']
            },
            'BPET': {
                'columns': ['1st Attempt', '2nd Attempt', '3rd Attempt', 'Event Wise Best'],
                'sub_events': ['5 KM Run', '60M Sprint', '9\' Ditch', 'H\' Rope', 'V\' Rope']
            },
            'Firing': {
                'columns': ['1st Attempt', '2nd Attempt'],
                'sub_events': ['300M SFTS', '100M Reflex', '50M SU', '200M SFTS', '100M LU', '100M SFTS (Night)', '15M BC']
            },
            'DST': {
                'columns': ['1st Attempt', '2nd Attempt', '3rd Attempt'],
                'sub_events': ['Turn Out & Bearing', 'WOC', 'DST W/O Arm', 'DST with Arm']
            },
            'BFC': {
                'columns': ['1st Attempt', '2nd Attempt'],
                'sub_events': ['Hindi (Theory)', 'Hindi (TMA)', 'English (Theory)', 'English (TMA)']
            }
        },
        'sub_events': {
            'PPT': ['2.4 KM Run', '100M Sprint', 'Chin Up', 'Sit Up', 'Toe Touch', '5 Mtr Shuttle'],
            'BPET': ['5 KM Run', '60M Sprint', '9\' Ditch', 'H\' Rope', 'V\' Rope'],
            'Firing': ['300M SFTS', '100M Reflex', '50M SU', '200M SFTS', '100M LU', '100M SFTS (Night)', '15M BC'],
            'DST': ['Turn Out & Bearing', 'WOC', 'DST W/O Arm', 'DST with Arm'],
            'MR_III': ['Outdoor Test', 'Indoor Test Written', 'Project Wks'],
            'BFC': ['Hindi (Theory)', 'Hindi (TMA)', 'English (Theory)', 'English (TMA)'],
            'PDP': ['PDP Test'],
            'FC_All': ['TGT IDEN', 'JUDGING DIST', 'OBSN TRG', 'FC Online 1st Attempt', 'FC Online 2nd Attempt', 'FC Online Best Attempt', 'CAMP TRG'],
        },
        'max_marks': {
            'PPT': {
                '2.4 KM Run': 20,
                '100M Sprint': 20,
                'Chin Up': 20,
                'Sit Up': 10,
                'Toe Touch': 20,
                '5 Mtr Shuttle': 10,
            },
            'BPET': {
                '5 KM Run': 40,
                '60M Sprint': 20,
                "9' Ditch": 10,
                "H' Rope": 20,
                "V' Rope": 10,
            },
            'Firing': {
                '300M SFTS': 4,
                '100M Reflex': 12,
                '50M SU': 9,
                '200M SFTS': 12,
                '100M LU': 10,
                '100M SFTS (Night)': 4,
                '15M BC': 5,
            },
            'DST': {
                'Turn Out & Bearing': 20,
                'WOC': 20,
                'DST W/O Arm': 60,
                'DST with Arm': 60,
            },
            'BFC': {
                'Hindi (Theory)': 100,
                'Hindi (TMA)': 20,
                'English (Theory)': 100,
                'English (TMA)': 20,
            },
            'PDP': {
                'PDP Test': 50,
            },
            'MR_III': {
                'Outdoor Test': 50,
                'Indoor Test Written': 90,
                'Project Wks': 10,
            },
            'FC_All': {
                'TGT IDEN': 10,
                'JUDGING DIST': 10,
                'OBSN TRG': 10,
                'FC Online 1st Attempt': 30,
                'FC Online 2nd Attempt': 30,
                'FC Online Best Attempt': 30,
                'CAMP TRG': 30,
            }
        },
        'readonly_events': {
        }
    },
    'B': {
        'name': 'TTS',
        'total_marks': 40,
        'categories': [
            ('theory', 'Theory & TMA'),
            ('practical', 'Practical Assessment'),
        ],
        'test_types': [
            ('BFC', 'BFC Test'),
            ('MR', 'MR'),
            ('PDP', 'PDP'),
        ],
        'test_to_category': {
            'BFC': 'theory',
            'MR': 'practical',
            'PDP': 'practical',
        },
        'sub_events': {
            'BFC': ['Hindi (Theory)', 'Hindi (TMA)', 'English (Theory)', 'English (TMA)'],
            'MR': ['Outdoor Test', 'Indoor Test Written', 'Project Wks'],
            'PDP': ['PDP Assessment'],
        },
        'sub_departments': {
            'DMV': {
                'name': 'TTS - DMV',
                'total_marks': 40,
                'overall_max_marks': 200,
                'categories': [
                    ('practical', 'Final Practical Test'),
                    ('driving', 'Final Driving Test'),
                    ('assessment', 'Assessment'),
                    ('screen_board', 'Screen Board'),
                    ('result', 'Final Result'),
                ],
                'test_types': [
                    ('DMV_PRACTICAL', 'Final Practical Test'),
                    ('DMV_DRIVING', 'Final Driving Test'),
                    ('DMV_ASSESSMENT', 'Final Assessment'),
                    ('DMV_SCREEN_BOARD', 'Screen Board'),
                    ('DMV_RESULT', 'Final Result Sheet'),
                ],
                'test_to_category': {
                    'DMV_PRACTICAL': 'practical',
                    'DMV_DRIVING': 'driving',
                    'DMV_ASSESSMENT': 'assessment',
                    'DMV_SCREEN_BOARD': 'screen_board',
                    'DMV_RESULT': 'result',
                },
                'sub_events': {
                    'DMV_PRACTICAL': [
                        'TATA 2.5 TON (15)',
                        'ALS 5/7.5 TON (15)',
                        'INDICATION & USE OF TOOLS (10)',
                        'OIL & LUBRICANTS (05)',
                        'INDICATION OF VEH PARTS (05)'
                    ],
                    'DMV_DRIVING': [
                        'STARTING & MARCHING PROCEDURE (10)',
                        'STEERING CONTROLL & OVER TAKE (15)',
                        'GEAR SHIFTING (15)',
                        'ROAD SENSE (05)',
                        'HAULTING PROCEDURE (05)'
                    ],
                    'DMV_ASSESSMENT': [
                        'Op of trde eqpt (10)',
                        'Maint of trde eqpt (05)',
                        'Initiatave (03)',
                        'Willingness to learn (02)',
                        'Willingness to take on additional respnsibilty (03)',
                        'Handling of veh during/before & after using veh (06)',
                        'Timely completion of work (03)',
                        'Handling of basic eqpt/tools (03)',
                        'A performance during diff type of task (04)',
                        'A performance during diff trg conditions (03)',
                        'Dedication of org (6)',
                        'Degree proficiency achived during conduct progrss test (4)',
                        'Degree proficiency achieved during conduct of practicals test (4)',
                        'Motivation (04)',
                        'Courage (03)',
                        'Timely completion of task (03)',
                        'Ability to carry out task unsupervised (03)',
                        'Feedback after completion of task (02)'
                    ],
                    'DMV_SCREEN_BOARD': [
                        'Mid Term Test (50)',
                        'Convert In 10 Mks (Mid Term)',
                        'Online Test (100)',
                        'Convert In 15 Mks',
                        'Job (40)',
                        'Convert In 05 Mks',
                        'Practical (60)',
                        'Convert In 10 Mks (Practical)',
                        'Grand Total (40)',
                        '% Age',
                        'Grading'
                    ],
                    'DMV_RESULT': [
                        'Online Test (100)',
                        'Practical Test (50)',
                        'Driving Test (50)',
                        'Total (200)',
                        '% Age',
                        'Grading',
                        'Convert 40 Marks'
                    ]
                },
                'max_marks': {
                    'DMV_PRACTICAL': {
                        'TATA 2.5 TON (15)': 15,
                        'ALS 5/7.5 TON (15)': 15,
                        'INDICATION & USE OF TOOLS (10)': 10,
                        'OIL & LUBRICANTS (05)': 5,
                        'INDICATION OF VEH PARTS (05)': 5
                    },
                    'DMV_DRIVING': {
                        'STARTING & MARCHING PROCEDURE (10)': 10,
                        'STEERING CONTROLL & OVER TAKE (15)': 15,
                        'GEAR SHIFTING (15)': 15,
                        'ROAD SENSE (05)': 5,
                        'HAULTING PROCEDURE (05)': 5
                    },
                    'DMV_ASSESSMENT': {
                        'Op of trde eqpt (10)': 10,
                        'Maint of trde eqpt (05)': 5,
                        'Initiatave (03)': 3,
                        'Willingness to learn (02)': 2,
                        'Willingness to take on additional respnsibilty (03)': 3,
                        'Handling of veh during/before & after using veh (06)': 6,
                        'Timely completion of work (03)': 3,
                        'Handling of basic eqpt/tools (03)': 3,
                        'A performance during diff type of task (04)': 4,
                        'A performance during diff trg conditions (03)': 3,
                        'Dedication of org (6)': 6,
                        'Degree proficiency achived during conduct progrss test (4)': 4,
                        'Degree proficiency achieved during conduct of practicals test (4)': 4,
                        'Motivation (04)': 4,
                        'Courage (03)': 3,
                        'Timely completion of task (03)': 3,
                        'Ability to carry out task unsupervised (03)': 3,
                        'Feedback after completion of task (02)': 2
                    },
                    'DMV_SCREEN_BOARD': {
                        'Mid Term Test (50)': 50,
                        'Convert In 10 Mks (Mid Term)': 10,
                        'Online Test (100)': 100,
                        'Convert In 15 Mks': 15,
                        'Job (40)': 40,
                        'Convert In 05 Mks': 5,
                        'Practical (60)': 60,
                        'Convert In 10 Mks (Practical)': 10,
                        'Grand Total (40)': 40,
                        '% Age': 100
                    },
                    'DMV_RESULT': {
                        'Online Test (100)': 100,
                        'Practical Test (50)': 50,
                        'Driving Test (50)': 50,
                        'Total (200)': 200
                    }
                },
                'readonly_events': {
                    'DMV_SCREEN_BOARD': [
                        'Convert In 10 Mks (Mid Term)',
                        'Convert In 15 Mks',
                        'Convert In 05 Mks',
                        'Convert In 10 Mks (Practical)',
                        'Grand Total (40)',
                        '% Age',
                        'Grading'
                    ]
                }
            },
            'OPEM': {
                'name': 'TTS - OPEM',
                'test_types': [
                    ('OPEM_MAINTENANCE', 'Maintenance Test'),
                    ('OPEM_PRACTICAL', 'Practical Test'),
                    ('OPEM_ASSESSMENT', 'Final Assessment'),
                    ('OPEM_SCREEN_BOARD', 'Screen Board'),
                    ('OPEM_RESULT', 'Final Result')
                ],
                'categories': [
                    ('maintenance', 'Maintenance'),
                    ('practical', 'Practical'),
                    ('assessment', 'Assessment'),
                    ('screen_board', 'Screen Board'),
                    ('result', 'Result')
                ],
                'test_to_category': {
                    'OPEM_MAINTENANCE': 'maintenance',
                    'OPEM_PRACTICAL': 'practical',
                    'OPEM_ASSESSMENT': 'assessment',
                    'OPEM_SCREEN_BOARD': 'screen_board',
                    'OPEM_RESULT': 'result'
                },
                'sub_events': {
                    'OPEM_ASSESSMENT': [
                        'Op of trde eqpt (10)',
                        'Maint of trde eqpt (05)',
                        'Initiatave (03)',
                        'Willingness to learn (02)',
                        'Willingness to take on additional respnsibilty (03)',
                        'Handling of veh during/before & after using veh (06)',
                        'Timely completion of work (03)',
                        'Handling of basic eqpt/tools (03)',
                        'A performance during diff type of task (04)',
                        'A performance during diff trg conditions (03)',
                        'Dedication of org (6)',
                        'Degree proficiency achived during conduct progrss test (4)',
                        'Degree proficiency achieved during conduct of practicals test (4)',
                        'Motivation (04)',
                        'Courage (03)',
                        'Timely completion of task (03)',
                        'Ability to carry out task unsupervised (03)',
                        'Feedback after completion of task (02)'
                    ],
                    'OPEM_MAINTENANCE': [
                        'Maint Test (10 MKS)',
                        'Name Of Parts (20 MKS)',
                        'Function Test (20 MKS)'
                    ],
                    'OPEM_PRACTICAL': [
                        'DOZER - CHECK BEFORE START (04 MKS)',
                        'DOZER - CONSTR OF INNITIAL CUTTING (08 MKS)',
                        'DOZER - CONSTR OF DCB (08 MKS)',
                        'TATA HITACHI - CHECK BEFORE START (02 MKS)',
                        'TATA HITACHI - LOADING OF SOIL ON TIPPER (04 MKS)',
                        'TATA HITACHI - DIGGING OF DRAINAGE (04 MKS)',
                        'SSL - CHECK BEFORE START (02 MKS)',
                        'SSL - DIGGING OF TRANCHES (04 MKS)',
                        'SSL - LOADING OF LOOSE SOIL ON TIPPER (04 MKS)',
                        'JCB - CHECK BEFORE START (02 MKS)',
                        'JCB - CONSTR OF DITCH 10X12 MTR (04 MKS)',
                        'JCB - LOADING OF LOOSE SOIL IN TIPPER (04 MKS)'
                    ],
                    'OPEM_SCREEN_BOARD': [
                        'Mid Term Test (50)',
                        'Convert In 10 Mks (Mid Term)',
                        'Online Test (100)',
                        'Convert In 15 Mks',
                        'Job (40)',
                        'Convert In 05 Mks',
                        'Practical (60)',
                        'Convert In 10 Mks (Practical)',
                        'Grand Total (40)',
                        '% Age',
                        'Grading'
                    ],
                    'OPEM_RESULT': [
                        'Written Test (100)',
                        'Practical Test (50)',
                        'Maintenance Test (50)',
                        'Total (200)',
                        '% Age',
                        'Grading',
                        'Convert 40 Marks'
                    ]
                },
                'max_marks': {
                    'OPEM_ASSESSMENT': {
                        'Op of trde eqpt (10)': 10,
                        'Maint of trde eqpt (05)': 5,
                        'Initiatave (03)': 3,
                        'Willingness to learn (02)': 2,
                        'Willingness to take on additional respnsibilty (03)': 3,
                        'Handling of veh during/before & after using veh (06)': 6,
                        'Timely completion of work (03)': 3,
                        'Handling of basic eqpt/tools (03)': 3,
                        'A performance during diff type of task (04)': 4,
                        'A performance during diff trg conditions (03)': 3,
                        'Dedication of org (6)': 6,
                        'Degree proficiency achived during conduct progrss test (4)': 4,
                        'Degree proficiency achieved during conduct of practicals test (4)': 4,
                        'Motivation (04)': 4,
                        'Courage (03)': 3,
                        'Timely completion of task (03)': 3,
                        'Ability to carry out task unsupervised (03)': 3,
                        'Feedback after completion of task (02)': 2
                    },
                    'OPEM_MAINTENANCE': {
                        'Maint Test (10 MKS)': 10,
                        'Name Of Parts (20 MKS)': 20,
                        'Function Test (20 MKS)': 20
                    },
                    'OPEM_PRACTICAL': {
                        'DOZER - CHECK BEFORE START (04 MKS)': 4,
                        'DOZER - CONSTR OF INNITIAL CUTTING (08 MKS)': 8,
                        'DOZER - CONSTR OF DCB (08 MKS)': 8,
                        'TATA HITACHI - CHECK BEFORE START (02 MKS)': 2,
                        'TATA HITACHI - LOADING OF SOIL ON TIPPER (04 MKS)': 4,
                        'TATA HITACHI - DIGGING OF DRAINAGE (04 MKS)': 4,
                        'SSL - CHECK BEFORE START (02 MKS)': 2,
                        'SSL - DIGGING OF TRANCHES (04 MKS)': 4,
                        'SSL - LOADING OF LOOSE SOIL ON TIPPER (04 MKS)': 4,
                        'JCB - CHECK BEFORE START (02 MKS)': 2,
                        'JCB - CONSTR OF DITCH 10X12 MTR (04 MKS)': 4,
                        'JCB - LOADING OF LOOSE SOIL IN TIPPER (04 MKS)': 4
                    },
                    'OPEM_SCREEN_BOARD': {
                        'Mid Term Test (50)': 50,
                        'Convert In 10 Mks (Mid Term)': 10,
                        'Online Test (100)': 100,
                        'Convert In 15 Mks': 15,
                        'Job (40)': 40,
                        'Convert In 05 Mks': 5,
                        'Practical (60)': 60,
                        'Convert In 10 Mks (Practical)': 10,
                        'Grand Total (40)': 40,
                        '% Age': 100
                    },
                    'OPEM_RESULT': {
                        'Written Test (100)': 100,
                        'Practical Test (50)': 50,
                        'Maintenance Test (50)': 50,
                        'Total (200)': 200
                    }
                },
                'readonly_events': {
                    'OPEM_SCREEN_BOARD': [
                        'Convert In 10 Mks (Mid Term)',
                        'Convert In 15 Mks',
                        'Convert In 05 Mks',
                        'Convert In 10 Mks (Practical)',
                        'Grand Total (40)',
                        '% Age',
                        'Grading'
                    ]
                },
                'total_marks': 40
            },
            'OTHER': {
                'name': 'TTS - Other Trades',
                'test_types': [
                    ('OTHER_ASSESSMENT', 'Final Assessment'),
                    ('OTHER_SCREEN_BOARD', 'Screen Board'),
                ],
                'categories': [
                    ('assessment', 'Assessment'),
                    ('screen_board', 'Screen Board'),
                ],
                'test_to_category': {
                    'OTHER_ASSESSMENT': 'assessment',
                    'OTHER_SCREEN_BOARD': 'screen_board',
                },
                'sub_events': {
                    'OTHER_ASSESSMENT': [
                        'Progressive knowledge of trade (04)',
                        'Creativity during OJT (04)',
                        'Quality of work (04)',
                        'Decision making during GP task (06)',
                        'Initiative (04)',
                        'Willingness to learn (04)',
                        'Estimation of store list and eqpt (04)',
                        'Adherence to orders during work execution (04)',
                        'Timely completion of assigned task (02)',
                        'Handling of trade eqpt/tools in assigned task (02)',
                        'Grasping subject (03)',
                        'Practical Application (04)',
                        'Dedication to Org (06)',
                        'Level of Skills Achieved (08)',
                        'Motivation (04)',
                        'Courage (03)',
                        'Timely Completion of Task (06)',
                        'Carryout Task Unsupervised (02)'
                    ],
                    'OTHER_SCREEN_BOARD': [
                        'Mid Term Test (50)',
                        'Convert In 10 Mks (Mid Term)',
                        'Online Test (100)',
                        'Convert In 15 Mks',
                        'Job (40)',
                        'Convert In 05 Mks',
                        'Practical (60)',
                        'Convert In 10 Mks (Practical)',
                        'Grand Total (40)',
                        '% Age',
                        'Grading'
                    ]
                },
                'max_marks': {
                    'OTHER_ASSESSMENT': {
                        'Progressive knowledge of trade (04)': 4,
                        'Creativity during OJT (04)': 4,
                        'Quality of work (04)': 4,
                        'Decision making during GP task (06)': 6,
                        'Initiative (04)': 4,
                        'Willingness to learn (04)': 4,
                        'Estimation of store list and eqpt (04)': 4,
                        'Adherence to orders during work execution (04)': 4,
                        'Timely completion of assigned task (02)': 2,
                        'Handling of trade eqpt/tools in assigned task (02)': 2,
                        'Grasping subject (03)': 3,
                        'Practical Application (04)': 4,
                        'Dedication to Org (06)': 6,
                        'Level of Skills Achieved (08)': 8,
                        'Motivation (04)': 4,
                        'Courage (03)': 3,
                        'Timely Completion of Task (06)': 6,
                        'Carryout Task Unsupervised (02)': 2
                    },
                    'OTHER_SCREEN_BOARD': {
                        'Mid Term Test (50)': 50,
                        'Convert In 10 Mks (Mid Term)': 10,
                        'Online Test (100)': 100,
                        'Convert In 15 Mks': 15,
                        'Job (40)': 40,
                        'Convert In 05 Mks': 5,
                        'Practical (60)': 60,
                        'Convert In 10 Mks (Practical)': 10,
                        'Grand Total (40)': 40,
                        '% Age': 100
                    }
                },
                'readonly_events': {
                    'OTHER_SCREEN_BOARD': [
                        'Convert In 10 Mks (Mid Term)',
                        'Convert In 15 Mks',
                        'Convert In 05 Mks',
                        'Convert In 10 Mks (Practical)',
                        'Grand Total (40)',
                        '% Age',
                        'Grading'
                    ]
                },
                'total_marks': 40
            }
        }
    },
    'C': {
        'name': 'CS',
        'total_marks': 80,
        'categories': [
            ('assessment', 'Assessment'),
            ('result', 'Final Result'),
            ('clerk_result', 'Final Result (Clerk)'),
        ],
        'test_types': [
            ('CS_ASSESSMENT', 'Assessment'),
            ('CS_RESULT', 'CS Final Result'),
            ('CS_CLERK_RESULT', 'Final Result (Clerk)'),
        ],
        'test_to_category': {
            'CS_ASSESSMENT': 'assessment',
            'CS_RESULT': 'result',
            'CS_CLERK_RESULT': 'clerk_result',
        },
        'sub_events': {
            'CS_ASSESSMENT': CS_ASSESSMENT_EVENTS,
            'CS_RESULT': [
                'TOET-I (25)',
                'TOET-II (25)',
                'TOTAL TOET (50)',
                '25% OF TOET (25)',
                'FE Online Exam (50)',
                'FE Prac (20)',
                'FE Total (70)',
                'BR Online Exam (40)',
                'BR Prac (25)',
                'BR Total (65)',
                'TOTAL (160)',
                'CONVERTED TO 40',
            ],
            'CS_CLERK_RESULT': [
                'Online (20)',
                'TPrac (20)',
                'Total (40)',
            ],
        },
        'max_marks': {
            'CS_ASSESSMENT': {
                **CS_ASSESSMENT_MAX_MARKS,
                'Total (40)': 40,
            },
            'CS_RESULT': {
                'TOET-I (25)': 25,
                'TOET-II (25)': 25,
                'TOTAL TOET (50)': 50,
                '25% OF TOET (25)': 25,
                'FE Online Exam (50)': 50,
                'FE Prac (20)': 20,
                'FE Total (70)': 70,
                'BR Online Exam (40)': 40,
                'BR Prac (25)': 25,
                'BR Total (65)': 65,
                'TOTAL (160)': 160,
                'CONVERTED TO 40': 40,
            },
            'CS_CLERK_RESULT': {
                'Online (20)': 20,
                'TPrac (20)': 20,
                'Total (40)': 40,
            },
        },
        'score_events': {
            'CS_ASSESSMENT': 'Total (40)',
            'CS_CLERK_RESULT': 'Total (40)',
        },
        'readonly_events': {
            'CS_RESULT': [
                'TOTAL TOET (50)',
                '25% OF TOET (25)',
                'FE Total (70)',
                'BR Total (65)',
                'TOTAL (160)',
                'CONVERTED TO 40',
            ],
            'CS_CLERK_RESULT': [
                'Total (40)',
            ],
        }
    },
    'D': {
        'name': 'Clerk',
        'total_marks': 40,
        'categories': [
            ('initial', 'Initial Test'),
            ('weekly', 'Weekly Tests'),
            ('final', 'Final Test'),
        ],
        'test_types': [
            ('CLK_INITIAL', 'Initial Test'),
            ('CLK_WEEKLY_1', '1st Weekly Test'),
            ('CLK_WEEKLY_2', '2nd Weekly Progress Test'),
            ('CLK_FINAL', 'Final Test'),
        ],
        'test_to_category': {
            'CLK_INITIAL': 'initial',
            'CLK_WEEKLY_1': 'weekly',
            'CLK_WEEKLY_2': 'weekly',
            'CLK_FINAL': 'final',
        },
        'sub_events': {
            'CLK_INITIAL': [
                'Academic Written (100)',
                'Computer Project Work (25)',
                'Marks Obtained (125)',
                'Percentage',
                'Pass/Fail',
            ],
            'CLK_WEEKLY_1': [
                'Tech Written (50)',
                'Academic Written (50)',
                'Computer Obj (25)',
                'Computer Prac (25)',
                'Computer Total (50)',
                'Typing 20 WPM',
                'Marks Obtained (150)',
                'Percentage',
                'Result',
                'Grading',
            ],
            'CLK_WEEKLY_2': [
                'Tech Online (115)',
                'Tech Proj HRMS (25)',
                'Academic Online (85)',
                'Computer Online (25)',
                'Computer Prac (25)',
                'Computer Total (50)',
                'Typing 20 WPM',
                'Marks Obtained (275)',
                'Percentage',
                'Result',
                'Grading',
            ],
            'CLK_FINAL': [
                'Tech Online (115)',
                'Tech Proj HRMS (25)',
                'Academic Online (85)',
                'Computer Online (25)',
                'Computer Prac (25)',
                'Computer Total (50)',
                'Extempore (25)',
                'Typing 20 WPM',
                'Marks Obtained (40)',
                'Percentage',
                'Result',
                'Grading',
            ],
        },
        'max_marks': {
            'CLK_INITIAL': {
                'Academic Written (100)': 100,
                'Computer Project Work (25)': 25,
                'Marks Obtained (125)': 125,
                'Percentage': 100,
            },
            'CLK_WEEKLY_1': {
                'Tech Written (50)': 50,
                'Academic Written (50)': 50,
                'Computer Obj (25)': 25,
                'Computer Prac (25)': 25,
                'Computer Total (50)': 50,
                'Typing 20 WPM': 200,
                'Marks Obtained (150)': 150,
                'Percentage': 100,
            },
            'CLK_WEEKLY_2': {
                'Tech Online (115)': 115,
                'Tech Proj HRMS (25)': 25,
                'Academic Online (85)': 85,
                'Computer Online (25)': 25,
                'Computer Prac (25)': 25,
                'Computer Total (50)': 50,
                'Typing 20 WPM': 200,
                'Marks Obtained (275)': 275,
                'Percentage': 100,
            },
            'CLK_FINAL': {
                'Tech Online (115)': 115,
                'Tech Proj HRMS (25)': 25,
                'Academic Online (85)': 85,
                'Computer Online (25)': 25,
                'Computer Prac (25)': 25,
                'Computer Total (50)': 50,
                'Extempore (25)': 25,
                'Typing 20 WPM': 200,
                'Marks Obtained (40)': 40,
                'Percentage': 100,
            },
        },
        'readonly_events': {
            'CLK_INITIAL': ['Marks Obtained (125)', 'Percentage', 'Pass/Fail'],
            'CLK_WEEKLY_1': ['Computer Total (50)', 'Marks Obtained (150)', 'Percentage', 'Result', 'Grading'],
            'CLK_WEEKLY_2': ['Computer Total (50)', 'Marks Obtained (275)', 'Percentage', 'Result', 'Grading'],
            'CLK_FINAL': ['Computer Total (50)', 'Marks Obtained (40)', 'Percentage', 'Result', 'Grading'],
        },
        'pass_marks': {
            'CLK_INITIAL': 57.5,
            'CLK_WEEKLY_1': 69,
            'CLK_WEEKLY_2': 126.5,
            'CLK_FINAL': 18.4,
        },
        'score_events': {
            'CLK_INITIAL': 'Marks Obtained (125)',
            'CLK_WEEKLY_1': 'Marks Obtained (150)',
            'CLK_WEEKLY_2': 'Marks Obtained (275)',
            'CLK_FINAL': 'Marks Obtained (40)',
        },
    }
}
def get_dept_config(dept_code, user=None):
    if dept_code == 'B' and user and hasattr(user, 'tts_trade'):
        trade = user.tts_trade
        sub_depts = DEPT_CONFIG['B'].get('sub_departments', {})
        if trade in sub_depts:
            return sub_depts[trade]
    return DEPT_CONFIG.get(dept_code, DEPT_CONFIG['A'])

def get_dept_total_marks(dept_code, user=None):
    return get_dept_config(dept_code, user).get('total_marks', 40)

def get_overall_total_marks(user=None):
    total = 0
    for code in DEPT_CONFIG.keys():
        if code == 'B' and user:
            total += get_dept_total_marks('B', user)
        else:
            total += DEPT_CONFIG[code].get('total_marks', 40)
    return total
