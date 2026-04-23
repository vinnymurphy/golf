import json
import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from scoring.models import Round, HoleScore, Course, Hole, TeeSet

class Command(BaseCommand):
    help = 'Imports golf rounds from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to the JSON file')

    def handle(self, *args, **options):
        file_path = options['json_file']
        
        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File {file_path} not found"))
            return

        with open(file_path, 'r') as f:
            data = json.load(f)

        for entry in data:
            try:
                user = User.objects.get(username=entry['username'].lower())
                course = Course.objects.get(name=entry['course'])
                
                # 1. Create the Round
                new_round = Round.objects.create(
                    user=user,
                    course=course,
                    date=entry['date'],
                    total_gross_score=entry['total_gross_score'],
                    completed_holes=entry['completed_holes']
                )

                # 2. Add Hole Scores if they exist
                if entry.get('hole_scores'):
                    tee_set = TeeSet.objects.get(course=course, name=entry['tee_set_name'])
                    # We grab holes 1-9 specifically for your Rochester 9-hole data
                    holes = Hole.objects.filter(tee_set=tee_set).order_by('hole_number')[:len(entry['hole_scores'])]
                    
                    for hole, score_val in zip(holes, entry['hole_scores']):
                        HoleScore.objects.create(
                            round=new_round,
                            hole=hole,
                            strokes=score_val
                        )
                
                self.stdout.write(self.style.SUCCESS(f"Imported round for {entry['username']}"))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to import {entry['username']}: {e}"))