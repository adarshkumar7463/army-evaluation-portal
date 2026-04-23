"""
Evaluation Constants - Department Configurations
"""

DEPT_CONFIG = {
    'A': {
        'name': 'Department A',
        'total_marks': 420,
        'categories': [
            ('on_field', 'On Field Training'),
            ('trade', 'Basic Trade Training'),
        ],
        'test_types': [
            ('physical', 'Physical Test'),
            ('weapon', 'Weapon Test'),
            ('field', 'Field Training'),
            ('assessment', 'Assessment'),
            ('viva', 'Viva'),
            ('ojt', 'On Job Training'),
            ('written', 'Written Exam'),
        ],
        'test_to_category': {
            'physical': 'on_field',
            'weapon': 'on_field',
            'field': 'on_field',
            'assessment': 'trade',
            'viva': 'trade',
            'ojt': 'trade',
            'written': 'trade',
        }
    },
    'B': {
        'name': 'Department B',
        'total_marks': 300,
        'categories': [
            ('on_field', 'On Field Training'),
            ('trade', 'Basic Trade Training'),
        ],
        'test_types': [
            ('physical', 'Physical Test'),
            ('weapon', 'Weapon Test'),
            ('field', 'Field Training'),
            ('viva', 'Viva'),
            ('written', 'Written Exam'),
        ],
        'test_to_category': {
            'physical': 'on_field',
            'weapon': 'on_field',
            'field': 'on_field',
            'viva': 'trade',
            'written': 'trade',
        }
    },
    'C': {
        'name': 'Department C',
        'total_marks': 360,
        'categories': [
            ('on_field', 'On Field Training'),
            ('trade', 'Basic Trade Training'),
        ],
        'test_types': [
            ('physical', 'Physical Test'),
            ('weapon', 'Weapon Test'),
            ('field', 'Field Training'),
            ('assessment', 'Assessment'),
            ('ojt', 'On Job Training'),
            ('written', 'Written Exam'),
        ],
        'test_to_category': {
            'physical': 'on_field',
            'weapon': 'on_field',
            'field': 'on_field',
            'assessment': 'trade',
            'ojt': 'trade',
            'written': 'trade',
        }
    },
    'D': {
        'name': 'Department D',
        'total_marks': 300,
        'categories': [
            ('on_field', 'On Field Training'),
            ('trade', 'Basic Trade Training'),
        ],
        'test_types': [
            ('physical', 'Physical Test'),
            ('weapon', 'Weapon Test'),
            ('field', 'Field Training'),
            ('assessment', 'Assessment'),
            ('written', 'Written Exam'),
        ],
        'test_to_category': {
            'physical': 'on_field',
            'weapon': 'on_field',
            'field': 'on_field',
            'assessment': 'trade',
            'written': 'trade',
        }
    }
}

def get_dept_total_marks(dept_code):
    return DEPT_CONFIG.get(dept_code, DEPT_CONFIG['A'])['total_marks']

def get_overall_total_marks():
    return sum(config['total_marks'] for config in DEPT_CONFIG.values())
