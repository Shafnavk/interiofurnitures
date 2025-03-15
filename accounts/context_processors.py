def user_processor(request):
    return {
        'user': request.user
    }