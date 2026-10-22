from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_branch'),
    ]

    operations = [
        migrations.AddField(
            model_name='roosterageestimate',
            name='chicken_detected',
            field=models.CharField(
                choices=[('yes', 'Yes'), ('no', 'No'), ('unassessed', 'Unable to determine')],
                default='unassessed',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='roosterageestimate',
            name='spur_visibility',
            field=models.CharField(
                choices=[
                    ('clear', 'Spurs clearly visible'),
                    ('partial', 'Partially visible'),
                    ('hidden', 'Hidden or not visible'),
                    ('unassessed', 'Not assessed'),
                ],
                default='unassessed',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='roosterageestimate',
            name='spur_length',
            field=models.CharField(
                choices=[
                    ('none', 'None visible'),
                    ('buds', 'Small buds'),
                    ('short', 'Short'),
                    ('medium', 'Medium'),
                    ('long', 'Long'),
                    ('unassessed', 'Not assessed'),
                ],
                default='unassessed',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='roosterageestimate',
            name='spur_thickness',
            field=models.CharField(
                choices=[
                    ('thin', 'Thin'),
                    ('moderate', 'Moderate'),
                    ('thick', 'Thick'),
                    ('unassessed', 'Not assessed'),
                ],
                default='unassessed',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='roosterageestimate',
            name='spur_point_shape',
            field=models.CharField(
                choices=[
                    ('rounded', 'Rounded or blunt'),
                    ('pointed', 'Sharp pointed'),
                    ('worn', 'Worn or irregular'),
                    ('unassessed', 'Not assessed'),
                ],
                default='unassessed',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='roosterageestimate',
            name='spur_curvature',
            field=models.CharField(
                choices=[
                    ('straight', 'Straight'),
                    ('slight', 'Slightly curved'),
                    ('curved', 'Strongly curved'),
                    ('unassessed', 'Not assessed'),
                ],
                default='unassessed',
                max_length=20,
            ),
        ),
    ]