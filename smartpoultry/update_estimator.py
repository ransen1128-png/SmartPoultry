from pathlib import Path

views_path = Path("core/views.py")
source = views_path.read_text(encoding="utf-8")

start_marker = (
    "@login_required(login_url='login')\n"
    "def rooster_age_estimator_view(request):"
)

end_marker = (
    "\n\n@login_required(login_url='login')\n"
    "def reports_view(request):"
)

if start_marker not in source:
    raise SystemExit("ERROR: Could not find the existing estimator function.")

start = source.index(start_marker)
end = source.find(end_marker, start)

if end == -1:
    raise SystemExit("ERROR: Could not find the end of the estimator function.")

new_function = '''@login_required(login_url='login')
def rooster_age_estimator_view(request):
    """Estimate chicken age from an uploaded spur image using the trained model."""
    from core.rooster_age_classifier import (
        model_is_ready,
        predict_rooster_age,
    )

    results = []

    if request.method == 'POST':
        photos = request.FILES.getlist('photos')

        if not photos:
            messages.error(request, 'Upload at least one image to continue.')

        for index, photo in enumerate(photos):
            photo_name = photo.name
            photo_analysis = analyze_rooster_photo(photo)
            prediction = None

            if model_is_ready() and photo_analysis['quality'] == 'good':
                try:
                    photo.seek(0)
                    prediction = predict_rooster_age(photo)
                except (OSError, ValueError, RuntimeError):
                    prediction = None

            if prediction:
                age_months = prediction['age_months']
                age_range = f'{age_months:.1f} months'

                evidence = (
                    f'The trained image model estimated the chicken age '
                    f'at {age_range}.'
                )

                reasoning = (
                    'The ResNet-18 model generated an age estimate by '
                    'comparing the uploaded image with patterns learned '
                    'from the labeled training images.'
                )

                confidence = 'Not calibrated'

                limitations = (
                    'This is an image-based estimate, not a confirmed age. '
                    'The model does not independently verify that a chicken '
                    'or spur is present and does not directly measure spur '
                    'length. Image angle, lighting, and differences between '
                    'the uploaded image and training images may affect '
                    'the prediction.'
                )

            else:
                age_range = 'Insufficient evidence'
                confidence = 'Not available'

                if photo_analysis['quality'] != 'good':
                    evidence = (
                        'No age estimate was provided because the image '
                        'did not pass the technical quality checks.'
                    )
                    reasoning = (
                        'The uploaded image may need better lighting, '
                        'resolution, contrast, or focus.'
                    )
                    limitations = (
                        f"{photo_analysis['summary']} "
                        'Upload a clear, well-lit spur photo.'
                    )

                elif not model_is_ready():
                    evidence = (
                        'No age estimate was provided because the trained '
                        'age-estimation model is unavailable.'
                    )
                    reasoning = 'The model could not be loaded.'
                    limitations = (
                        'Check that the trained model file is present '
                        'and can be loaded.'
                    )

                else:
                    evidence = (
                        'The model could not generate a prediction '
                        'for this image.'
                    )
                    reasoning = 'The image prediction was unsuccessful.'
                    limitations = (
                        'Try uploading another clear, well-lit image.'
                    )

            record_data = {
                'user': request.user,
                'photo_name': photo_name,
                'chicken_detected': 'unassessed',
                'spur_visibility': 'unassessed',
                'spur_length': 'unassessed',
                'spur_thickness': 'unassessed',
                'spur_point_shape': 'unassessed',
                'spur_curvature': 'unassessed',
                'secondary_clues': '',
                'estimated_age_range': age_range,
                'spur_observations': evidence,
                'reasoning': reasoning,
                'confidence': confidence,
                'limitations': limitations,
            }

            photo.seek(0)
            record_data['photo'] = photo

            record = RoosterAgeEstimate.objects.create(**record_data)

            results.append({
                'number': index + 1,
                'id': record.id,
                'photo_name': photo_name,
                'chicken_detected': record.get_chicken_detected_display(),
                'spur_visibility': record.get_spur_visibility_display(),
                'spur_length_assessment': (
                    'Not directly measured by the current model.'
                ),
                'estimated_age_range': record.estimated_age_range,
                'spur_observations': evidence,
                'image_assessment': photo_analysis['summary'],
                'reasoning': record.reasoning,
                'confidence': record.confidence,
                'limitations': record.limitations,
            })

        if results:
            successful = sum(
                1 for result in results
                if result['estimated_age_range'] != 'Insufficient evidence'
            )

            messages.success(
                request,
                f'Processed {len(results)} image(s). '
                f'{successful} age estimate(s) generated.'
            )

    saved_estimates = (
        RoosterAgeEstimate.objects
        .filter(user=request.user)
        .exclude(photo='')
        [:20]
    )

    return render(request, 'rooster_age_estimator.html', {
        'results': results,
        'saved_estimates': saved_estimates,
        'model_ready': model_is_ready(),
    })
'''

updated_source = source[:start] + new_function + source[end:]
views_path.write_text(updated_source, encoding="utf-8")

print("SUCCESS: Age estimator updated.")
print("Other views were preserved.")
print(f"Updated file: {views_path.resolve()}")
