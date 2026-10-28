// GREENLINE beta signup: paste into script.google.com, press Run, allow access.
// Creates the Google Form + a Google Sheet that collects the answers.
// Players 12 or younger are sent to a parent or guardian page, so we never collect a young kid's own email.
function makeGreenlineBetaForm() {
  var form = FormApp.create('GREENLINE Beta Signup');
  form.setDescription(
    'GREENLINE is a co-op cube zombie shooter for iPhone and Android by Tufufal Studios. ' +
    'Glo fuel leaked, the town turned into cube zombies, and you and up to 3 friends fight back.\n\n' +
    'Sign up and we will email you a beta invite when testing opens. ' +
    'Players 12 or younger: ask a parent or guardian to fill this in with their email. ' +
    'We only use emails for beta invites and game news, never sold or shared.');
  form.setConfirmationMessage('You are on the list! Watch your email for your beta invite. Follow us for clips and updates: TikTok @playgreenline, Instagram @playgreenline2026.');
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setLimitOneResponsePerUser(false);

  var ageItem = form.addMultipleChoiceItem().setTitle('How old is the player?').setRequired(true);

  var parentPage = form.addPageBreakItem().setTitle('Parent or guardian')
    .setHelpText('Players 12 or younger need a parent or guardian to sign up. We will send the beta invite to you, not to your child.');
  form.addTextItem().setTitle('Parent or guardian email').setRequired(true)
    .setValidation(FormApp.createTextValidation().requireTextIsEmail().build());
  form.addCheckboxItem().setTitle('Parent or guardian check').setRequired(true)
    .setChoiceValues(['I am the player\'s parent or guardian and I am OK with GREENLINE beta emails']);

  var playerPage = form.addPageBreakItem().setTitle('Your email');
  form.addTextItem().setTitle('Email').setRequired(true)
    .setValidation(FormApp.createTextValidation().requireTextIsEmail().build());

  var aboutPage = form.addPageBreakItem().setTitle('About the player');
  parentPage.setGoToPage(aboutPage);

  form.addMultipleChoiceItem().setTitle('What phone will they play on?').setRequired(true)
    .setChoiceValues(['iPhone', 'Android', 'Both']);

  form.addTextItem().setTitle('Phone model (optional)')
    .setHelpText('Like iPhone 13 or Galaxy S22. Helps us test on lots of phones.');

  form.addCheckboxItem().setTitle('Which of these do they play? (optional)')
    .setChoiceValues(['Fortnite', 'Brawl Stars', 'Pixel Gun 3D', 'Roblox', 'Minecraft', 'Call of Duty Zombies'])
    .showOtherOption(true);

  form.addMultipleChoiceItem().setTitle('Where did you find GREENLINE?')
    .setChoiceValues(['TikTok', 'Instagram', 'YouTube', 'A friend', 'School'])
    .showOtherOption(true);

  ageItem.setChoices([
    ageItem.createChoice('12 or younger', parentPage),
    ageItem.createChoice('13 to 15', playerPage),
    ageItem.createChoice('16 to 17', playerPage),
    ageItem.createChoice('18 or older', playerPage)
  ]);

  var sheet = SpreadsheetApp.create('GREENLINE Beta Signups');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, sheet.getId());

  Logger.log('SHARE THIS LINK: ' + form.getPublishedUrl());
  Logger.log('Edit form: ' + form.getEditUrl());
  Logger.log('Answers sheet: ' + sheet.getUrl());
}
